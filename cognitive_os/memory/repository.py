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

    def save_knowledge_units(self, units: List[KnowledgeUnit]) -> None:
        with self._connect() as conn:
            for ku in units:
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_units(id, payload, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (ku.id, json.dumps(asdict(ku), ensure_ascii=False)),
                )

    def load_knowledge_units(self) -> List[KnowledgeUnit]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM knowledge_units ORDER BY id").fetchall()
        return [KnowledgeUnit.from_dict(json.loads(row[0])) for row in rows]

    def load_knowledge_units_with_timestamps(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload, updated_at FROM knowledge_units ORDER BY id"
            ).fetchall()
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
                "INSERT INTO judgements(goal, payload) VALUES (?, ?)",
                (judgement.goal, json.dumps(judgement.decisions, ensure_ascii=False)),
            )

    def load_judgements(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, goal, payload, created_at FROM judgements ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": row[0],
                    "goal": row[1],
                    "decisions": json.loads(row[2]),
                    "created_at": row[3],
                }
            )
        return result

    @staticmethod
    def parse_datetime(raw: str) -> datetime:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
