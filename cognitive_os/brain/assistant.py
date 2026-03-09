from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cognitive_os.brain.llm_client import LLMBrainClient
from cognitive_os.brain.toolkit import BrainToolkit
from cognitive_os.commands import BuiltinCommands, SlashCommandParser, SlashCommand, CommandResult
from cognitive_os.context.document_pinning import Citation, CitationManager, DocumentPinningManager
from cognitive_os.rag.chat_history import ChatHistoryManager, ChatMessage
from cognitive_os.rag.query_rewriter import QueryRewriter, RewriteResult
from cognitive_os.rag.reranker import Reranker, RerankerFactory
from cognitive_os.rag.workflow_config import RetrievalConfig, WorkflowConfig
from cognitive_os.vector.vector_cache import VectorCache


@dataclass(slots=True)
class AssistantResult:
    answer: str
    tool_trace: List[Dict[str, Any]]
    retrieved: List[Dict[str, Any]]
    model: str
    used_remote_model: bool
    query_rewrite: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    rerank_used: bool = False
    citations: List[Dict[str, Any]] = field(default_factory=list)
    command_result: Optional[Dict[str, Any]] = None
    pinned_documents: List[Dict[str, Any]] = field(default_factory=list)


class PersonalKnowledgeAssistant:
    """Model as brain, knowledge as base, tools as hands/feet."""

    def __init__(
        self,
        toolkit: BrainToolkit,
        llm: Optional[LLMBrainClient] = None,
        retrieval_config: Optional[RetrievalConfig] = None,
        chat_history_manager: Optional[ChatHistoryManager] = None,
        reranker: Optional[Reranker] = None,
        vector_cache: Optional[VectorCache] = None,
    ) -> None:
        self.toolkit = toolkit
        self.llm = llm or LLMBrainClient()
        self.retrieval_config = retrieval_config or RetrievalConfig.default()
        self.chat_history = chat_history_manager or ChatHistoryManager()
        self.query_rewriter = QueryRewriter(llm_client=llm)
        self._reranker = reranker
        self._vector_cache = vector_cache
        self._slash_parser = SlashCommandParser()
        self._pinning_manager = DocumentPinningManager()
        self._citation_manager = CitationManager(self._pinning_manager)
        BuiltinCommands.register_handlers(self._slash_parser)

    def set_llm_client(self, llm: LLMBrainClient) -> None:
        self.llm = llm
        self.query_rewriter = QueryRewriter(llm_client=llm)

    def set_retrieval_config(self, config: RetrievalConfig) -> None:
        self.retrieval_config = config

    def _get_reranker(self) -> Optional[Reranker]:
        if self._reranker:
            return self._reranker
        if self.retrieval_config and self.retrieval_config.workflow_config and self.retrieval_config.workflow_config.reranker_config:
            return RerankerFactory.create(
                supplier=self.retrieval_config.workflow_config.reranker_config.supplier,
                model=self.retrieval_config.workflow_config.reranker_config.model,
            )
        return None

    def _get_vector_cache(self) -> Optional[VectorCache]:
        if self._vector_cache is None:
            self._vector_cache = VectorCache()
        return self._vector_cache

    def handle_query(
        self,
        user_query: str,
        scenario: str = "general",
        knowledge_base_id: int | None = None,
        session_id: Optional[str] = None,
        use_history: bool = True,
        use_rewrite: bool = True,
        use_rerank: bool = True,
        web_mode: bool = False,
    ) -> AssistantResult:
        import traceback

        try:
            return self._handle_query_impl(
                user_query=user_query,
                scenario=scenario,
                knowledge_base_id=knowledge_base_id,
                session_id=session_id,
                use_history=use_history,
                use_rewrite=use_rewrite,
                use_rerank=use_rerank,
                web_mode=web_mode,
            )
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[ERROR] handle_query failed: {e}")
            print(f"[TRACE] {tb[:500]}")
            return AssistantResult(
                answer=f"处理查询时出错: {str(e)}",
                tool_trace=[],
                retrieved=[],
                model=self.llm.model,
                used_remote_model=False,
                query_rewrite=None,
                session_id=session_id or "",
                rerank_used=False,
            )

    def _handle_query_impl(
        self,
        user_query: str,
        scenario: str = "general",
        knowledge_base_id: int | None = None,
        session_id: Optional[str] = None,
        use_history: bool = True,
        use_rewrite: bool = True,
        use_rerank: bool = True,
        web_mode: bool = False,
    ) -> AssistantResult:
        tool_trace: List[Dict[str, Any]] = []
        rewrite_result: Optional[RewriteResult] = None
        rerank_used = False
        command_result: Optional[CommandResult] = None

        # 安全检查：确保 retrieval_config 不为 None
        if self.retrieval_config is None:
            self.retrieval_config = RetrievalConfig.default()

        slash_command, cleaned_query = self._slash_parser.parse(user_query)
        if slash_command.command_type.value != "custom" or cleaned_query != user_query:
            context = {
                "session_id": session_id,
                "chat_history": self.chat_history,
                "toolkit": self.toolkit,
                "knowledge_base_id": knowledge_base_id,
                "retrieved": [],
            }
            command_result = self._slash_parser.execute(slash_command, context)
            tool_trace.append({
                "tool": "slash_command",
                "command": slash_command.name,
                "result": command_result.to_dict(),
            })

            if command_result.actions:
                if "enable_web_browsing" in command_result.actions:
                    web_mode = True
                if "reset_history" in command_result.actions and session_id:
                    self.chat_history.delete_session(session_id)
                if "pin_document" in command_result.actions:
                    doc_name = command_result.data.get("pin_document")
                    if doc_name:
                        self._pin_document_by_name(doc_name, session_id or "default")
                if "unpin_document" in command_result.actions:
                    doc_name = command_result.data.get("unpin_document")
                    if doc_name:
                        self._unpin_document_by_name(doc_name, session_id or "default")

            if slash_command.name in ["reset", "clear", "help"]:
                return AssistantResult(
                    answer=command_result.message,
                    tool_trace=tool_trace,
                    retrieved=[],
                    model="system",
                    used_remote_model=False,
                    session_id=session_id,
                    command_result=command_result.to_dict(),
                )

        actual_query = cleaned_query if cleaned_query else user_query

        if session_id:
            self.chat_history.add_message(session_id, "user", user_query)

        retrieval_query = actual_query
        if use_rewrite and self.retrieval_config.use_query_rewrite:
            rewrite_result = self.query_rewriter.rewrite(actual_query)
            retrieval_query = rewrite_result.rewritten_query
            tool_trace.append({
                "tool": "query_rewrite",
                "original": actual_query,
                "rewritten": retrieval_query,
                "keywords": getattr(rewrite_result, 'keywords', []),
                "intent": getattr(rewrite_result, 'intent', 'general'),
            })

        history_context = ""
        if use_history and session_id and self.retrieval_config.use_history:
            history_context = self.chat_history.get_history_context(session_id, max_messages=5)
            if history_context:
                tool_trace.append({
                    "tool": "history_context",
                    "session_id": session_id,
                    "context_length": len(history_context),
                })

        retrieved = self.toolkit.retrieve_knowledge(
            retrieval_query,
            top_k=self.retrieval_config.top_k,
            knowledge_base_id=knowledge_base_id,
        )

        if web_mode:
            web_results = self._fetch_web_results(actual_query)
            retrieved.extend(web_results)
            tool_trace.append({
                "tool": "web_browsing",
                "results": len(web_results),
            })

        pinned_docs = self._pinning_manager.get_pinned_documents(session_id or "default")
        if pinned_docs:
            pinned_results = self._get_pinned_content(pinned_docs)
            retrieved = pinned_results + retrieved
            tool_trace.append({
                "tool": "pinned_documents",
                "count": len(pinned_docs),
            })

        tool_trace.append({
            "tool": "vector_retrieve",
            "input": retrieval_query,
            "hits": len(retrieved),
        })

        if use_rerank and self.retrieval_config.use_reranker and retrieved:
            reranker = self._get_reranker()
            if reranker:
                candidates = [{"text": r["text"], "score": r["score"], "metadata": r} for r in retrieved]
                top_n = self.retrieval_config.workflow_config.reranker_config.top_n if self.retrieval_config.workflow_config and self.retrieval_config.workflow_config.reranker_config else 5
                reranked = reranker.rerank(actual_query, candidates, top_n=top_n)
                retrieved = [
                    {
                        "id": r.metadata.get("id", ""),
                        "score": round(r.score, 4),
                        "original_score": round(r.original_score, 4),
                        "topic": r.metadata.get("topic", ""),
                        "document_id": r.metadata.get("document_id"),
                        "filename": r.metadata.get("filename", ""),
                        "knowledge_base_id": r.metadata.get("knowledge_base_id"),
                        "text": r.text[:320],
                        "source": r.metadata.get("source", "private"),
                        "confidence": r.metadata.get("confidence", 0.5),
                    }
                    for r in reranked
                ]
                rerank_used = True
                tool_trace.append({
                    "tool": "rerank",
                    "model": self.retrieval_config.workflow_config.reranker_config.model if self.retrieval_config.workflow_config and self.retrieval_config.workflow_config.reranker_config else "local",
                    "top_n": len(retrieved),
                })

        citations = self._citation_manager.build_citations(
            retrieved, session_id or "default", max_citations=10
        )

        should_run_cognition = any(
            k in actual_query for k in ["建议", "决策", "下一步", "策略", "回复", "方案", "总结"]
        ) or scenario == "marketing_customer_service_assistant"

        cognition_result: Dict[str, Any] = {}
        if should_run_cognition:
            cognition_result = self.toolkit.run_cognition(goal=actual_query, scenario=scenario)
            tool_trace.append({"tool": "cognition_loop", "decisions": len(cognition_result.get("decisions", []))})

        context_block = "\n".join([f"- {x['topic']} | score={x['score']} | {x['text']}" for x in retrieved[:8]])
        decision_block = f"\nDecision constraints: {cognition_result.get('decisions', [])}" if cognition_result else ""
        history_block = f"\n对话历史:\n{history_context}\n" if history_context else ""
        citations_block = f"\n引用来源:\n{self._citation_manager.format_citations_inline(citations[:5])}" if citations else ""

        has_relevant_knowledge = len(retrieved) > 0 and any(r.get("score", 0) > 0.3 for r in retrieved[:3])
        
        is_simple_greeting = any(greeting in actual_query.lower() for greeting in ["你好", "您好", "hi", "hello", "hey", "早上好", "下午好", "晚上好", "嗨"])
        is_simple_chit_chat = any(term in actual_query.lower() for term in ["怎么样", "好吗", "是吗", "对吧", "在吗", "忙吗", "有空吗"])
        is_knowledge_query = any(term in actual_query.lower() for term in ["什么", "怎么", "如何", "为什么", "哪里", "哪个", "多少", "吗?", "是?", "?", "？"])
        
        if has_relevant_knowledge:
            is_knowledge_query = True

        if is_simple_greeting or (not has_relevant_knowledge and not is_knowledge_query and not should_run_cognition):
            system_prompt = "你是友好的个人知识服务助手。请用自然、亲切的方式回应用户的问候或简单对话。"
            user_prompt = f"{history_block}用户: {actual_query}\n请友好地回应。"
        elif has_relevant_knowledge or should_run_cognition:
            system_prompt = (
                "你是个人知识服务助手核心大脑。必须优先遵循知识体系创新：语义检索 + 置信度/来源/冲突加权。\n"
                "当有相关知识检索结果或决策约束时，请按以下结构化输出：\n"
                "1) 结论\n"
                "2) 依据（引用检索到的知识）\n"
                "3) 风险提示（如有）\n"
                "4) 下一步行动清单（如有）\n"
                "5) 引用来源（在回答末尾列出）"
            )
            user_prompt = (
                f"{history_block}"
                f"用户需求: {actual_query}\n"
                f"场景: {scenario}\n"
                f"知识检索结果:\n{context_block}\n"
                f"{decision_block}\n"
                f"{citations_block}\n"
            )
        else:
            system_prompt = (
                "你是个人知识服务助手。用户的问题没有找到相关知识库内容，请友好地告知用户，"
                "并建议用户可以先上传相关文档或使用更具体的关键词搜索。"
            )
            user_prompt = f"{history_block}用户: {actual_query}\n知识库中暂未找到相关内容。"

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
        llm_resp = self.llm.chat(messages)

        if session_id:
            self.chat_history.add_message(session_id, "assistant", llm_resp.content)

        return AssistantResult(
            answer=llm_resp.content,
            tool_trace=tool_trace,
            retrieved=retrieved,
            model=llm_resp.model,
            used_remote_model=llm_resp.used_remote,
            query_rewrite={
                "original": getattr(rewrite_result, 'original_query', actual_query),
                "rewritten": getattr(rewrite_result, 'rewritten_query', actual_query),
                "keywords": getattr(rewrite_result, 'keywords', []),
                "intent": getattr(rewrite_result, 'intent', 'general'),
            } if rewrite_result else None,
            session_id=session_id,
            rerank_used=rerank_used,
            citations=[c.to_dict() for c in citations],
            command_result=command_result.to_dict() if command_result else None,
            pinned_documents=[p.to_dict() for p in pinned_docs],
        )

    def _fetch_web_results(self, query: str) -> List[Dict[str, Any]]:
        try:
            from cognitive_os.skills.web_skills import WebBrowsingSkill

            skill = WebBrowsingSkill()
            units = skill.execute({"query": query, "max_results": 3})
            return [
                {
                    "id": u.id,
                    "text": u.content.get("summary", "")[:500],
                    "score": 0.4,
                    "topic": u.content.get("topic", "Web Result"),
                    "filename": u.content.get("url", ""),
                    "source": "public",
                    "confidence": 0.4,
                }
                for u in units
            ]
        except Exception:
            return []

    def _pin_document_by_name(self, doc_name: str, session_id: str) -> bool:
        return True

    def _unpin_document_by_name(self, doc_name: str, session_id: str) -> bool:
        return True

    def _get_pinned_content(self, pinned_docs: List) -> List[Dict[str, Any]]:
        return []

    def pin_document(
        self,
        document_id: int,
        filename: str,
        session_id: str,
        knowledge_base_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        result = self._pinning_manager.pin_document(
            session_id=session_id,
            document_id=document_id,
            filename=filename,
            knowledge_base_id=knowledge_base_id,
        )
        return result.to_dict()

    def unpin_document(self, document_id: int, session_id: str) -> bool:
        return self._pinning_manager.unpin_document(document_id, session_id)

    def get_pinned_documents(self, session_id: str) -> List[Dict[str, Any]]:
        docs = self._pinning_manager.get_pinned_documents(session_id)
        return [d.to_dict() for d in docs]

    def create_session(self, knowledge_base_id: Optional[int] = None) -> str:
        import uuid

        session_id = str(uuid.uuid4())
        self.chat_history.create_session(session_id, knowledge_base_id)
        return session_id

    def get_session_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        messages = self.chat_history.get_recent_messages(session_id, limit)
        return [m.to_dict() for m in messages]

    def get_available_commands(self) -> List[str]:
        return self._slash_parser.get_available_commands()
