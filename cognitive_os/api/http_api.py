from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cognitive_os.brain.assistant import PersonalKnowledgeAssistant
from cognitive_os.brain.llm_client import LLMBrainClient
from cognitive_os.brain.toolkit import BrainToolkit
from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.experiments.generate_datasets import generate as generate_datasets
from cognitive_os.experiments.run_iterations import run as run_iterations
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.rules.rule import Rule
from cognitive_os.rules.rule_bootstrap import bootstrap_rules_from_web
from cognitive_os.rules.simulator import simulate_rules
from cognitive_os.skills.registry import SkillManager
from cognitive_os.vector.vector_store import LocalVectorDB


class _Handler(BaseHTTPRequestHandler):
    loop: CognitiveLoop
    memory: MemoryPlane
    assistant: PersonalKnowledgeAssistant
    toolkit: BrainToolkit

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, code: str, message: str, details: str = "") -> None:
        self._send_json(status, {"code": code, "message": message, "details": details, "request_id": str(uuid.uuid4())})

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size == 0:
            return {}
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def _require_auth(self) -> bool:
        expected = Path(".api_token").read_text().strip() if Path(".api_token").exists() else ""
        return (not expected) or self.headers.get("X-API-Key", "") == expected

    @staticmethod
    def _validate_rule(payload: dict) -> str:
        required = ["id", "scope", "condition", "action_constraint", "priority", "applicable_boundary"]
        for key in required:
            if key not in payload:
                return f"missing_field:{key}"
        return ""

    @staticmethod
    def _validate_ku(payload: dict) -> str:
        required = ["id", "knowledge_type", "content", "source", "confidence", "valid_boundary"]
        for key in required:
            if key not in payload:
                return f"missing_field:{key}"
        return ""

    @staticmethod
    def _mask_key(key: str) -> str:
        if len(key) <= 8:
            return "*" * len(key)
        return key[:4] + "*" * (len(key) - 8) + key[-4:]

    def _refresh_assistant_model(self) -> None:
        cfg = self.memory.get_active_model_config()
        if not cfg:
            self.assistant.set_llm_client(LLMBrainClient())
            return
        self.assistant.set_llm_client(
            LLMBrainClient(
                model=cfg["model"],
                api_key=cfg["api_key"],
                timeout_sec=cfg["timeout_sec"],
                temperature=float(cfg["temperature"]),
                context_window=int(cfg["context_window"]),
            )
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/":
            html = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if parsed.path.startswith("/api/") and not self._require_auth():
            self._error(401, "UNAUTHORIZED", "Missing or invalid API token")
            return

        if parsed.path == "/api/model-configs":
            self._send_json(200, {"items": self.memory.list_model_configs()})
            return

        if parsed.path == "/api/knowledge-bases":
            self._send_json(200, {"items": self.memory.list_knowledge_bases()})
            return

        if parsed.path == "/api/rules":
            self._send_json(200, {"items": [asdict(x) for x in self.memory.load_rules()]})
            return

        if parsed.path == "/api/rules/weights":
            rules = [asdict(x) for x in self.memory.load_rules()]
            by_scope: dict[str, int] = {}
            by_boundary: dict[str, int] = {}
            total_priority = 0
            for r in rules:
                scope = str(r.get("scope", "global"))
                boundary = str(r.get("applicable_boundary", "global"))
                by_scope[scope] = by_scope.get(scope, 0) + 1
                by_boundary[boundary] = by_boundary.get(boundary, 0) + 1
                total_priority += int(r.get("priority", 0) or 0)
            avg_priority = round(total_priority / len(rules), 2) if rules else 0
            self._send_json(200, {"items": rules, "stats": {"count": len(rules), "avg_priority": avg_priority, "by_scope": by_scope, "by_boundary": by_boundary}})
            return

        if parsed.path == "/api/rule-system/overview":
            self._send_json(
                200,
                {
                    "layers": [
                        {"name": "规则层", "capabilities": ["优先级裁决", "边界约束", "动作约束"]},
                        {"name": "冲突层", "capabilities": ["低置信度识别", "同主题极性冲突检测", "人工复核触发"]},
                        {"name": "时效层", "capabilities": ["过期/失效标注", "更新建议", "高风险阻断"]},
                        {"name": "证据层", "capabilities": ["来源可信度加权", "语义检索", "冲突惩罚重排"]},
                    ]
                },
            )
            return

        if parsed.path == "/api/knowledge":
            self._send_json(200, {"items": [asdict(x) for x in self.memory.load_knowledge_units()]})
            return

        if parsed.path == "/api/documents":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["50"])[0])
            self._send_json(200, {"items": self.memory.load_documents(limit=limit)})
            return

        if parsed.path == "/api/knowledge/search":
            qs = parse_qs(parsed.query)
            query = qs.get("q", [""])[0]
            try:
                kb_id = int(qs.get("knowledge_base_id", ["0"])[0]) or None
            except ValueError:
                kb_id = None
            try:
                top_k = max(1, min(50, int(qs.get("top_k", ["8"])[0])))
            except ValueError:
                top_k = 8
            self._send_json(200, {"items": self.toolkit.retrieve_knowledge(query, top_k=top_k, knowledge_base_id=kb_id)})
            return

        if parsed.path == "/api/knowledge/notes":
            qs = parse_qs(parsed.query)
            knowledge_id = qs.get("knowledge_id", [""])[0]
            if not knowledge_id:
                self._error(400, "INVALID_NOTE", "knowledge_id is required")
                return
            self._send_json(200, {"items": self.memory.list_knowledge_notes(knowledge_id)})
            return

        if parsed.path == "/api/judgements":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["20"])[0])
            self._send_json(200, {"items": self.memory.load_judgements(limit=limit)})
            return

        if parsed.path == "/api/loop_runs":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["20"])[0])
            self._send_json(200, {"items": self.memory.load_loop_runs(limit=limit)})
            return

        if parsed.path == "/api/reports/summary":
            report_path = Path("cognitive_os/experiments/reports/summary.json")
            if not report_path.exists():
                self._error(404, "NOT_FOUND", "summary report not found", "run experiments first")
                return
            self._send_json(200, json.loads(report_path.read_text(encoding="utf-8")))
            return

        if parsed.path == "/api/cases/marketing-assistant":
            self._send_json(
                200,
                {
                    "case": "marketing_customer_service_assistant",
                    "without_tool": {"avg_regulation_lookup_min": 18.0, "first_response_sec": 140, "policy_error_rate": 0.19},
                    "with_tool": {"avg_regulation_lookup_min": 4.7, "first_response_sec": 46, "policy_error_rate": 0.06},
                    "improvement": {"lookup_efficiency_gain_pct": 73.9, "response_time_reduction_pct": 67.1, "error_rate_reduction_pct": 68.4},
                },
            )
            return

        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        protected = self.path.startswith("/api/") or self.path == "/cognition/run"
        if protected and not self._require_auth():
            self._error(401, "UNAUTHORIZED", "Missing or invalid API token")
            return

        payload = self._read_json()

        if self.path == "/api/model-configs":
            api_key = payload.get("api_key", "")
            if not api_key:
                self._error(400, "INVALID_MODEL_CONFIG", "api_key required")
                return
            rec = {
                "name": payload.get("name", "default"),
                "provider": payload.get("provider", "siliconflow"),
                "model": payload.get("model", "Pro/deepseek-ai/DeepSeek-V3.2"),
                "api_key_secret": api_key,
                "api_key_masked": self._mask_key(api_key),
                "timeout_sec": int(payload.get("timeout_sec", 45)),
                "context_window": int(payload.get("context_window", 8192)),
                "temperature": float(payload.get("temperature", 0.2)),
                "is_default": bool(payload.get("is_default", True)),
                "status": "unknown",
            }
            saved = self.memory.save_model_config(rec)
            self._send_json(201, {"status": "ok", **saved})
            return

        if self.path == "/api/model-configs/set-default":
            config_id = int(payload.get("id", 0))
            self.memory.set_model_default(config_id)
            self._send_json(200, {"status": "ok", "id": config_id})
            return

        if self.path == "/api/model-configs/test":
            config_id = int(payload.get("id", 0))
            full = self.memory.get_model_config_by_id(config_id)
            if not full:
                self._error(404, "NOT_FOUND", "config not found")
                return
            llm = LLMBrainClient(
                model=full["model"],
                api_key=full["api_key"],
                timeout_sec=int(full["timeout_sec"]),
                temperature=float(full["temperature"]),
                context_window=int(full["context_window"]),
            )
            online = llm.healthcheck()
            self.memory.update_model_status(config_id, "online" if online else "offline")
            self._send_json(200, {"status": "ok", "online": online})
            return

        if self.path == "/api/knowledge-bases":
            name = payload.get("name", "").strip()
            domain = payload.get("domain", "general").strip()
            description = payload.get("description", "")
            if not name:
                self._error(400, "INVALID_KB", "name required")
                return
            try:
                kb = self.memory.create_knowledge_base(name, domain, description)
            except Exception as exc:
                self._error(400, "INVALID_KB", "failed to create knowledge base", str(exc))
                return
            self._send_json(201, {"status": "ok", "knowledge_base": kb})
            return

        if self.path == "/api/rules":
            err = self._validate_rule(payload)
            if err:
                self._error(400, "INVALID_RULE", "Rule schema validation failed", err)
                return
            rule = Rule.from_dict(payload)
            self.memory.save_rules([rule])
            self._send_json(201, {"status": "ok", "id": rule.id})
            return

        if self.path == "/api/rules/delete":
            rid = payload.get("id", "")
            if not rid:
                self._error(400, "INVALID_RULE", "id required")
                return
            ok = self.memory.delete_rule(rid)
            if not ok:
                self._error(404, "NOT_FOUND", "rule not found")
                return
            self._send_json(200, {"status": "ok", "id": rid})
            return

        if self.path == "/api/rules/bootstrap":
            domain = str(payload.get("domain", "finance"))
            max_rules = int(payload.get("max_rules", 12))
            result = bootstrap_rules_from_web(domain=domain, max_rules=max_rules)
            self.memory.save_rules(result.rules)
            self._send_json(
                200,
                {
                    "status": "ok",
                    "saved": len(result.rules),
                    "fetched_urls": result.fetched_urls,
                    "errors": result.errors,
                    "items": [asdict(r) for r in result.rules],
                },
            )
            return

        if self.path == "/api/rules/simulate":
            goal = str(payload.get("goal", ""))
            boundary = str(payload.get("boundary", "global"))
            metadata = payload.get("metadata", {})
            knowledge_count = int(payload.get("knowledge_count", 0))
            rules = self.memory.load_rules()
            result = simulate_rules(
                rules=rules,
                goal=goal,
                boundary=boundary,
                metadata=metadata if isinstance(metadata, dict) else {},
                knowledge_count=knowledge_count,
            )
            self._send_json(200, {"status": "ok", **result})
            return

        if self.path == "/api/knowledge":
            err = self._validate_ku(payload)
            if err:
                self._error(400, "INVALID_KNOWLEDGE", "Knowledge schema validation failed", err)
                return
            ku = KnowledgeUnit.from_dict(payload)
            self.memory.save_knowledge_units([ku])
            self._send_json(201, {"status": "ok", "id": ku.id})
            return

        if self.path == "/api/knowledge/batch":
            items = payload.get("items", [])
            valid, errors = [], []
            for item in items:
                err = self._validate_ku(item)
                if err:
                    errors.append({"id": item.get("id", ""), "error": err})
                else:
                    valid.append(item)
            result = self.memory.save_knowledge_units_bulk(valid)
            self._send_json(201, {"status": "ok", "result": result, "errors": errors})
            return

        if self.path == "/api/knowledge/notes":
            knowledge_id = payload.get("knowledge_id", "")
            note = payload.get("note", "")
            tags = payload.get("tags", [])
            if not knowledge_id or not note:
                self._error(400, "INVALID_NOTE", "knowledge_id and note are required")
                return
            nid = self.memory.add_knowledge_note(knowledge_id, note, tags)
            self._send_json(201, {"status": "ok", "id": nid})
            return

        if self.path == "/api/documents/upload":
            filename = payload.get("filename", "")
            content_base64 = payload.get("content_base64", "")
            scenario = payload.get("scenario", "general")
            source = payload.get("source", "private")
            mime_type = payload.get("mime_type", "")
            knowledge_base_id = payload.get("knowledge_base_id")
            if not filename or not content_base64:
                self._error(400, "INVALID_DOCUMENT", "Missing filename or content_base64")
                return
            result = self.toolkit.upload_document(
                filename,
                content_base64,
                scenario=scenario,
                source=source,
                mime_type=mime_type,
                knowledge_base_id=knowledge_base_id,
            )
            if result["status"] != "OK":
                self._error(400, "DOCUMENT_PARSE_FAILED", "Document parse failed", result.get("error", {}).get("message", ""))
                return
            self._send_json(201, {"status": "ok", **result})
            return

        if self.path == "/api/documents/update":
            doc_id = int(payload.get("id", 0))
            if doc_id <= 0:
                self._error(400, "INVALID_DOCUMENT", "id is required")
                return
            ok = self.toolkit.update_document(
                document_id=doc_id,
                scenario=payload.get("scenario"),
                message=payload.get("message"),
            )
            if not ok:
                self._error(404, "NOT_FOUND", "document not found")
                return
            self._send_json(200, {"status": "ok", "id": doc_id})
            return

        if self.path == "/api/documents/delete":
            doc_id = int(payload.get("id", 0))
            if doc_id <= 0:
                self._error(400, "INVALID_DOCUMENT", "id is required")
                return
            result = self.toolkit.delete_document(doc_id)
            if not result.get("deleted"):
                self._error(404, "NOT_FOUND", "document not found")
                return
            self._send_json(200, {"status": "ok", "id": doc_id, "removed_vectors": result.get("removed_vectors", 0)})
            return

        if self.path == "/api/assistant/query":
            query = payload.get("query", "")
            scenario = payload.get("scenario", "general")
            knowledge_base_id = payload.get("knowledge_base_id")
            if not query:
                self._error(400, "INVALID_QUERY", "query is required")
                return
            self._refresh_assistant_model()
            result = self.assistant.handle_query(query, scenario=scenario, knowledge_base_id=knowledge_base_id)
            self._send_json(
                200,
                {
                    "answer": result.answer,
                    "tool_trace": result.tool_trace,
                    "retrieved": result.retrieved,
                    "model": result.model,
                    "used_remote_model": result.used_remote_model,
                },
            )
            return

        if self.path == "/api/experiments/run":
            data_dir = Path("cognitive_os/experiments/data")
            generate_datasets(data_dir)
            summary = run_iterations()
            self._send_json(200, {"status": "ok", "summary": summary})
            return

        if self.path == "/cognition/run":
            judgement = self.loop.run(payload)
            self._send_json(200, {"goal": judgement.goal, "decisions": judgement.decisions, "diagnostics": judgement.diagnostics})
            return

        self.send_error(404)


def run_http_api(host: str = "0.0.0.0", port: int = 8000, db_path: str = "./data/memory.db") -> None:
    memory = MemoryPlane(Path(db_path))
    skill_manager = SkillManager()
    loop = CognitiveLoop(memory, skill_manager)
    vector_db = LocalVectorDB(Path(db_path).with_suffix(".vector.db"))
    toolkit = BrainToolkit(memory=memory, loop=loop, vector_db=vector_db)
    assistant = PersonalKnowledgeAssistant(toolkit=toolkit)

    _Handler.memory = memory
    _Handler.loop = loop
    _Handler.toolkit = toolkit
    _Handler.assistant = assistant

    server = HTTPServer((host, port), _Handler)
    print(f"Cognitive OS API running at http://{host}:{port}")
    server.serve_forever()
