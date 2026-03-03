from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any, Dict, List

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.rules.rule import Rule
from cognitive_os.skills.registry import SkillManager




def _validate_knowledge_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = ["id", "knowledge_type", "content", "source"]
    missing = [k for k in required if k not in payload]
    if missing:
        return {"ok": False, "error": f"missing_fields:{','.join(missing)}"}

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_confidence"}

    if not 0.0 <= confidence <= 1.0:
        return {"ok": False, "error": "confidence_out_of_range"}

    return {"ok": True}


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
            validation = _validate_knowledge_payload(payload)
            if not validation["ok"]:
                self._send_json(400, {"status": "error", "error": validation["error"]})
                return

            ku = KnowledgeUnit.from_dict(payload)
            result = self.memory.save_knowledge_units_bulk([ku])
            if result["failed"]:
                self._send_json(409, {"status": "duplicate", "id": ku.id, "result": result})
                return
            self._send_json(201, {"status": "ok", "id": ku.id})
            return

        if self.path == "/api/knowledge/batch":
            payload = self._read_json()
            if not isinstance(payload, list):
                self._send_json(400, {"status": "error", "error": "payload_must_be_array"})
                return

            valid_units: List[KnowledgeUnit] = []
            per_item: List[Dict[str, Any]] = []
            for item in payload:
                if not isinstance(item, dict):
                    per_item.append({"id": None, "ok": False, "error": "item_must_be_object"})
                    continue

                validation = _validate_knowledge_payload(item)
                if not validation["ok"]:
                    per_item.append({"id": item.get("id"), "ok": False, "error": validation["error"]})
                    continue

                valid_units.append(KnowledgeUnit.from_dict(item))
                per_item.append({"id": item.get("id"), "ok": True})

            persistence_result = self.memory.save_knowledge_units_bulk(valid_units)
            failed_by_id = {entry["id"]: entry["reason"] for entry in persistence_result["failed"]}
            for item in per_item:
                if item.get("id") in failed_by_id:
                    item["ok"] = False
                    item["error"] = failed_by_id[item["id"]]

            self._send_json(201, {
                "status": "ok",
                "inserted_ids": persistence_result["inserted_ids"],
                "failed": persistence_result["failed"],
                "results": per_item,
            })
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
