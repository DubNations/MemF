from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from cognitive_os.ontology.ontology_engine import KnowledgeGraph
from cognitive_os.ontology.ontology_entity import KnowledgeUnit, OntologyEntity, OntologyRelation
from cognitive_os.rules.rule import Rule
from cognitive_os.rules.rule_engine import Judgement


@dataclass(slots=True)
class MemoryPlane:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS knowledge_units (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    payload_hash TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ontology_entities (
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS judgements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    diagnostics TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS loop_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    boundary TEXT NOT NULL,
                    skill_report TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    format TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sections INTEGER NOT NULL,
                    text_length INTEGER NOT NULL,
                    scenario TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def save_rules(self, rules: List[Rule]) -> None:
        with self._connect() as conn:
            for rule in rules:
                conn.execute(
                    "INSERT OR REPLACE INTO rules(id, payload, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (rule.id, json.dumps(asdict(rule), ensure_ascii=False)),
                )

    def load_rules(self) -> List[Rule]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM rules ORDER BY id").fetchall()
        return [Rule.from_dict(json.loads(row[0])) for row in rows]

    @staticmethod
    def _payload_hash(payload: Dict[str, Any]) -> str:
        return str(abs(hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))))

    def save_knowledge_units(self, units: List[KnowledgeUnit]) -> None:
        self.save_knowledge_units_bulk([asdict(unit) for unit in units])

    def save_knowledge_units_bulk(self, payloads: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        inserted: List[str] = []
        skipped: List[str] = []
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                for payload in payloads:
                    ku = KnowledgeUnit.from_dict(payload)
                    raw = asdict(ku)
                    phash = self._payload_hash(raw)
                    existing = conn.execute(
                        "SELECT payload_hash FROM knowledge_units WHERE id = ?",
                        (ku.id,),
                    ).fetchone()
                    if existing and existing[0] == phash:
                        skipped.append(ku.id)
                        continue
                    conn.execute(
                        "INSERT OR REPLACE INTO knowledge_units(id, payload, payload_hash, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                        (ku.id, json.dumps(raw, ensure_ascii=False), phash),
                    )
                    inserted.append(ku.id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {"inserted": inserted, "skipped": skipped}

    def load_knowledge_units(self) -> List[KnowledgeUnit]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM knowledge_units ORDER BY id").fetchall()
        return [KnowledgeUnit.from_dict(json.loads(row[0])) for row in rows]

    def load_knowledge_units_with_timestamps(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload, updated_at FROM knowledge_units ORDER BY id").fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row[0])
            payload["updated_at"] = row[1]
            result.append(payload)
        return result

    def load_ontology_entities(self) -> List[OntologyEntity]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM ontology_entities ORDER BY name").fetchall()
        entities: List[OntologyEntity] = []
        for row in rows:
            payload = json.loads(row[0])
            payload["relations"] = [OntologyRelation(**rel) for rel in payload.get("relations", [])]
            entities.append(OntologyEntity(**payload))
        return entities

    def save_ontology_entities(self, entities: List[OntologyEntity]) -> None:
        with self._connect() as conn:
            for entity in entities:
                payload = {
                    "name": entity.name,
                    "type": entity.type,
                    "attributes": entity.attributes,
                    "relations": [asdict(rel) for rel in entity.relations],
                }
                conn.execute(
                    "INSERT OR REPLACE INTO ontology_entities(name, payload, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (entity.name, json.dumps(payload, ensure_ascii=False)),
                )

    def write_back(self, knowledge_graph: KnowledgeGraph, judgement: Judgement) -> None:
        self.save_knowledge_units(list(knowledge_graph.knowledge_units.values()))
        self.save_ontology_entities(list(knowledge_graph.entities.values()))
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO judgements(goal, payload, diagnostics) VALUES (?, ?, ?)",
                (
                    judgement.goal,
                    json.dumps(judgement.decisions, ensure_ascii=False),
                    json.dumps(judgement.diagnostics, ensure_ascii=False),
                ),
            )

    def save_loop_run(self, goal: str, boundary: str, skill_report: List[Dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO loop_runs(goal, boundary, skill_report) VALUES (?, ?, ?)",
                (goal, boundary, json.dumps(skill_report, ensure_ascii=False)),
            )

    def load_loop_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, goal, boundary, skill_report, created_at FROM loop_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "goal": row[1],
                "boundary": row[2],
                "skill_report": json.loads(row[3]),
                "created_at": row[4],
            }
            for row in rows
        ]

    def load_judgements(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, goal, payload, diagnostics, created_at FROM judgements ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": row[0],
                    "goal": row[1],
                    "decisions": json.loads(row[2]),
                    "diagnostics": json.loads(row[3]),
                    "created_at": row[4],
                }
            )
        return result


    def save_document_record(self, metadata: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents(filename, format, status, sections, text_length, scenario, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    metadata.get("filename", ""),
                    metadata.get("format", ""),
                    metadata.get("status", ""),
                    int(metadata.get("sections", 0)),
                    int(metadata.get("text_length", 0)),
                    metadata.get("scenario", ""),
                    metadata.get("message", ""),
                ),
            )

    def load_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, filename, format, status, sections, text_length, scenario, message, created_at FROM documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "filename": row[1],
                "format": row[2],
                "status": row[3],
                "sections": row[4],
                "text_length": row[5],
                "scenario": row[6],
                "message": row[7],
                "created_at": row[8],
            }
            for row in rows
        ]


    @staticmethod
    def parse_datetime(raw: str) -> datetime:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
