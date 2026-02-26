from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.skills.registry import SkillManager


class _Handler(BaseHTTPRequestHandler):
    loop: CognitiveLoop

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/cognition/run":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        judgement = self.loop.run(payload)
        data = json.dumps({"goal": judgement.goal, "decisions": judgement.decisions}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_http_api(host: str = "0.0.0.0", port: int = 8000, db_path: str = "./data/memory.db") -> None:
    memory = MemoryPlane(Path(db_path))
    skill_manager = SkillManager()
    _Handler.loop = CognitiveLoop(memory, skill_manager)
    server = HTTPServer((host, port), _Handler)
    server.serve_forever()
