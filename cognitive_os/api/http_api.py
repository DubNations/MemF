from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cognitive_os.core.cognition_loop import CognitiveLoop
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

    def _read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size == 0:
            return {}
        return json.loads(self.rfile.read(size).decode("utf-8"))

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
        if self.path == "/api/rules":
            payload = self._read_json()
            rule = Rule.from_dict(payload)
            self.memory.save_rules([rule])
            self._send_json(201, {"status": "ok", "id": rule.id})
            return

        if self.path == "/api/knowledge":
            payload = self._read_json()
            ku = KnowledgeUnit.from_dict(payload)
            self.memory.save_knowledge_units([ku])
            self._send_json(201, {"status": "ok", "id": ku.id})
            return

        if self.path == "/cognition/run":
            payload = self._read_json()
            judgement = self.loop.run(payload)
            self._send_json(200, {"goal": judgement.goal, "decisions": judgement.decisions})
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
