from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cognitive_os.brain.llm_client import LLMBrainClient
from cognitive_os.brain.toolkit import BrainToolkit


@dataclass(slots=True)
class AssistantResult:
    answer: str
    tool_trace: List[Dict[str, Any]]
    retrieved: List[Dict[str, Any]]
    model: str
    used_remote_model: bool


class PersonalKnowledgeAssistant:
    """Model as brain, knowledge as base, tools as hands/feet."""

    def __init__(self, toolkit: BrainToolkit, llm: Optional[LLMBrainClient] = None) -> None:
        self.toolkit = toolkit
        self.llm = llm or LLMBrainClient()

    def set_llm_client(self, llm: LLMBrainClient) -> None:
        self.llm = llm

    def handle_query(self, user_query: str, scenario: str = "general", knowledge_base_id: int | None = None) -> AssistantResult:
        retrieved = self.toolkit.retrieve_knowledge(user_query, top_k=8, knowledge_base_id=knowledge_base_id)
        tool_trace: List[Dict[str, Any]] = [{"tool": "vector_retrieve", "input": user_query, "hits": len(retrieved)}]

        should_run_cognition = any(
            k in user_query for k in ["建议", "决策", "下一步", "策略", "回复", "方案", "总结"]
        ) or scenario == "marketing_customer_service_assistant"

        cognition_result: Dict[str, Any] = {}
        if should_run_cognition:
            cognition_result = self.toolkit.run_cognition(goal=user_query, scenario=scenario)
            tool_trace.append({"tool": "cognition_loop", "decisions": len(cognition_result.get("decisions", []))})

        context_block = "\n".join([f"- {x['topic']} | score={x['score']} | {x['text']}" for x in retrieved])
        decision_block = f"\nDecision constraints: {cognition_result.get('decisions', [])}" if cognition_result else ""

        messages = [
            {
                "role": "system",
                "content": (
                    "你是个人知识服务助手核心大脑。必须优先遵循知识体系创新：语义检索 + 置信度/来源/冲突加权。"
                    "输出需要包含：结论、依据、风险、下一步行动。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户需求: {user_query}\n"
                    f"场景: {scenario}\n"
                    f"知识检索结果:\n{context_block}\n"
                    f"{decision_block}\n"
                    "请输出结构：1) 结论 2) 依据 3) 风险提示 4) 下一步行动清单"
                ),
            },
        ]
        llm_resp = self.llm.chat(messages)
        return AssistantResult(
            answer=llm_resp.content,
            tool_trace=tool_trace,
            retrieved=retrieved,
            model=llm_resp.model,
            used_remote_model=llm_resp.used_remote,
        )
