from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.experiments.generate_datasets import generate as generate_datasets
from cognitive_os.experiments.run_iterations import run as run_iterations
from cognitive_os.ingestion.document_pipeline import DocumentPipeline
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.rules.rule import Rule
from cognitive_os.skills.registry import SkillManager


class _Handler(BaseHTTPRequestHandler):
    loop: CognitiveLoop
    memory: MemoryPlane

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, code: str, message: str, details: str = "") -> None:
        self._send_json(
            status,
            {
                "code": code,
                "message": message,
                "details": details,
                "request_id": str(uuid.uuid4()),
            },
        )

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size == 0:
            return {}
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def _require_auth(self) -> bool:
        expected = os.getenv("COGNITIVE_OS_API_TOKEN", "")
        if not expected:
            return True
        return self.headers.get("X-API-Key", "") == expected

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

        if parsed.path == "/api/rules":
            self._send_json(200, {"items": [asdict(x) for x in self.memory.load_rules()]})
            return

        if parsed.path == "/api/knowledge":
            self._send_json(200, {"items": [asdict(x) for x in self.memory.load_knowledge_units()]})
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

        if parsed.path == "/api/documents":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["50"])[0])
            self._send_json(200, {"items": self.memory.load_documents(limit=limit)})
            return

        if parsed.path == "/api/cases/marketing-assistant":
            self._send_json(
                200,
                {
                    "case": "marketing_customer_service_assistant",
                    "without_tool": {
                        "avg_regulation_lookup_min": 18.0,
                        "first_response_sec": 140,
                        "policy_error_rate": 0.19,
                    },
                    "with_tool": {
                        "avg_regulation_lookup_min": 4.7,
                        "first_response_sec": 46,
                        "policy_error_rate": 0.06,
                    },
                    "improvement": {
                        "lookup_efficiency_gain_pct": 73.9,
                        "response_time_reduction_pct": 67.1,
                        "error_rate_reduction_pct": 68.4,
                    },
                    "value_points": [
                        "国家-企业-部门制度统一检索",
                        "规章冲突识别与追溯",
                        "回复建议可解释与可复核",
                    ],
                },
            )
            return

        if parsed.path == "/api/reports/summary":
            report_path = Path("cognitive_os/experiments/reports/summary.json")
            if not report_path.exists():
                self._error(404, "NOT_FOUND", "summary report not found", "run experiments first")
                return
            self._send_json(200, json.loads(report_path.read_text(encoding="utf-8")))
            return

        if parsed.path == "/api/scenario/finance":
            items = self.memory.load_judgements(limit=5)
            self._send_json(
                200,
                {
                    "scenario": "finance_risk_assessment",
                    "description": "Kernel 用于贷款风险预审，低置信知识由 skill 补齐，规则输出可审计约束。",
                    "recent_results": items,
                },
            )
            return

        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        protected = self.path.startswith("/api/") or self.path == "/cognition/run"
        if protected and not self._require_auth():
            self._error(401, "UNAUTHORIZED", "Missing or invalid API token")
            return

        if self.path == "/api/rules":
            payload = self._read_json()
            err = self._validate_rule(payload)
            if err:
                self._error(400, "INVALID_RULE", "Rule schema validation failed", err)
                return
            rule = Rule.from_dict(payload)
            self.memory.save_rules([rule])
            self._send_json(201, {"status": "ok", "id": rule.id})
            return

        if self.path == "/api/documents/upload":
            payload = self._read_json()
            filename = payload.get("filename", "")
            content_base64 = payload.get("content_base64", "")
            scenario = payload.get("scenario", "general")
            source = payload.get("source", "private")

            if not filename or not content_base64:
                self._error(400, "INVALID_DOCUMENT", "Missing filename or content_base64")
                return

            parse_result, text = DocumentPipeline.parse_base64_document(filename, content_base64)
            metadata = DocumentPipeline.map_document_metadata(parse_result, scenario)
            self.memory.save_document_record(metadata)

            if parse_result.status != "OK":
                self._error(400, "DOCUMENT_PARSE_FAILED", "Document parse failed", parse_result.message)
                return

            units = DocumentPipeline.to_knowledge_units(filename, text, scenario=scenario, source=source)
            ingestion = self.memory.save_knowledge_units_bulk([asdict(x) for x in units])
            self._send_json(201, {"status": "ok", "document": metadata, "knowledge_ingestion": ingestion})
            return

        if self.path == "/api/knowledge":
            payload = self._read_json()
            err = self._validate_ku(payload)
            if err:
                self._error(400, "INVALID_KNOWLEDGE", "Knowledge schema validation failed", err)
                return
            ku = KnowledgeUnit.from_dict(payload)
            self.memory.save_knowledge_units([ku])
            self._send_json(201, {"status": "ok", "id": ku.id})
            return

        if self.path == "/api/knowledge/batch":
            payload = self._read_json()
            items = payload.get("items", [])
            valid = []
            errors = []
            for item in items:
                err = self._validate_ku(item)
                if err:
                    errors.append({"id": item.get("id", ""), "error": err})
                else:
                    valid.append(item)
            result = self.memory.save_knowledge_units_bulk(valid)
            self._send_json(201, {"status": "ok", "result": result, "errors": errors})
            return

        if self.path == "/api/experiments/run":
            data_dir = Path("cognitive_os/experiments/data")
            generate_datasets(data_dir)
            summary = run_iterations()
            self._send_json(200, {"status": "ok", "summary": summary})
            return

        if self.path == "/cognition/run":
            payload = self._read_json()
            judgement = self.loop.run(payload)
            self._send_json(
                200,
                {
                    "goal": judgement.goal,
                    "decisions": judgement.decisions,
                    "diagnostics": judgement.diagnostics,
                },
            )
            return

        self.send_error(404)


def run_http_api(host: str = "0.0.0.0", port: int = 8000, db_path: str = "./data/memory.db") -> None:
    memory = MemoryPlane(Path(db_path))
    skill_manager = SkillManager()
    _Handler.memory = memory
    _Handler.loop = CognitiveLoop(memory, skill_manager)
    server = HTTPServer((host, port), _Handler)
    print(f"Cognitive OS API running at http://{host}:{port}")
    server.serve_forever()
