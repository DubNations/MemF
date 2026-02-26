from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

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
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_units (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ontology_entities (
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
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
                    "INSERT OR REPLACE INTO rules(id, payload) VALUES (?, ?)",
                    (rule.id, json.dumps(asdict(rule), ensure_ascii=False)),
                )

    def load_rules(self) -> List[Rule]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM rules").fetchall()
        return [Rule.from_dict(json.loads(row[0])) for row in rows]


    def save_knowledge_units(self, units: List[KnowledgeUnit]) -> None:
        with self._connect() as conn:
            for ku in units:
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_units(id, payload) VALUES (?, ?)",
                    (ku.id, json.dumps(asdict(ku), ensure_ascii=False)),
                )

    def load_knowledge_units(self) -> List[KnowledgeUnit]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM knowledge_units").fetchall()
        return [KnowledgeUnit.from_dict(json.loads(row[0])) for row in rows]

    def load_ontology_entities(self) -> List[OntologyEntity]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM ontology_entities").fetchall()
        entities: List[OntologyEntity] = []
        for row in rows:
            payload = json.loads(row[0])
            payload["relations"] = [OntologyRelation(**rel) for rel in payload.get("relations", [])]
            entities.append(OntologyEntity(**payload))
        return entities

    def write_back(self, knowledge_graph: KnowledgeGraph, judgement: Judgement) -> None:
        with self._connect() as conn:
            for ku in knowledge_graph.knowledge_units.values():
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_units(id, payload) VALUES (?, ?)",
                    (ku.id, json.dumps(asdict(ku), ensure_ascii=False)),
                )
            for entity in knowledge_graph.entities.values():
                payload = {
                    "name": entity.name,
                    "type": entity.type,
                    "attributes": entity.attributes,
                    "relations": [asdict(rel) for rel in entity.relations],
                }
                conn.execute(
                    "INSERT OR REPLACE INTO ontology_entities(name, payload) VALUES (?, ?)",
                    (entity.name, json.dumps(payload, ensure_ascii=False)),
                )
            conn.execute(
                "INSERT INTO judgements(goal, payload) VALUES (?, ?)",
                (judgement.goal, json.dumps(judgement.decisions, ensure_ascii=False)),
            )
