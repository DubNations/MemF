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
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    domain TEXT NOT NULL,
                    description TEXT NOT NULL,
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
                    knowledge_base_id INTEGER,
                    mime_type TEXT NOT NULL DEFAULT '',
                    file_size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS model_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    api_key_masked TEXT NOT NULL,
                    api_key_secret TEXT NOT NULL,
                    timeout_sec INTEGER NOT NULL,
                    context_window INTEGER NOT NULL,
                    temperature REAL NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS knowledge_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    knowledge_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self._migrate_schema(conn)

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Backfill columns for existing local databases created by older versions."""
        migrations: Dict[str, Dict[str, str]] = {
            "documents": {
                "knowledge_base_id": "INTEGER",
                "mime_type": "TEXT NOT NULL DEFAULT ''",
                "file_size_bytes": "INTEGER NOT NULL DEFAULT 0",
            },
            "model_configs": {
                "status": "TEXT NOT NULL DEFAULT 'unknown'",
            },
        }
        for table, columns in migrations.items():
            existing = self._table_columns(conn, table)
            for col, ddl in columns.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

    # ----- rules -----
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

    # ----- KB management -----
    def create_knowledge_base(self, name: str, domain: str, description: str) -> Dict[str, Any]:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO knowledge_bases(name, domain, description) VALUES (?, ?, ?)",
                (name, domain, description),
            )
        return {"id": cur.lastrowid, "name": name, "domain": domain, "description": description}

    def list_knowledge_bases(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, domain, description, created_at FROM knowledge_bases ORDER BY id DESC"
            ).fetchall()
        return [
            {"id": r[0], "name": r[1], "domain": r[2], "description": r[3], "created_at": r[4]}
            for r in rows
        ]

    # ----- Model config -----
    def save_model_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._connect() as conn:
            if payload.get("is_default"):
                conn.execute("UPDATE model_configs SET is_default = 0")
            cur = conn.execute(
                """
                INSERT INTO model_configs(name, provider, model, api_key_masked, api_key_secret, timeout_sec, context_window, temperature, is_default, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["name"],
                    payload["provider"],
                    payload["model"],
                    payload["api_key_masked"],
                    payload["api_key_secret"],
                    int(payload.get("timeout_sec", 45)),
                    int(payload.get("context_window", 8192)),
                    float(payload.get("temperature", 0.2)),
                    1 if payload.get("is_default") else 0,
                    payload.get("status", "unknown"),
                ),
            )
        return {"id": cur.lastrowid}

    def set_model_default(self, config_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE model_configs SET is_default = 0")
            conn.execute("UPDATE model_configs SET is_default = 1 WHERE id = ?", (config_id,))

    def update_model_status(self, config_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE model_configs SET status = ? WHERE id = ?", (status, config_id))

    def list_model_configs(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, provider, model, api_key_masked, timeout_sec, context_window, temperature, is_default, status, created_at FROM model_configs ORDER BY id DESC"
            ).fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "provider": r[2],
                "model": r[3],
                "api_key_masked": r[4],
                "timeout_sec": r[5],
                "context_window": r[6],
                "temperature": r[7],
                "is_default": bool(r[8]),
                "status": r[9],
                "created_at": r[10],
            }
            for r in rows
        ]

    def get_model_config_by_id(self, config_id: int) -> Dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, provider, model, api_key_secret, timeout_sec, context_window, temperature, is_default, status FROM model_configs WHERE id = ?",
                (config_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "provider": row[2],
            "model": row[3],
            "api_key": row[4],
            "timeout_sec": row[5],
            "context_window": row[6],
            "temperature": row[7],
            "is_default": bool(row[8]),
            "status": row[9],
        }

    def get_active_model_config(self) -> Dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, provider, model, api_key_secret, timeout_sec, context_window, temperature FROM model_configs WHERE is_default = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT id, name, provider, model, api_key_secret, timeout_sec, context_window, temperature FROM model_configs ORDER BY id DESC LIMIT 1"
                ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "provider": row[2],
            "model": row[3],
            "api_key": row[4],
            "timeout_sec": row[5],
            "context_window": row[6],
            "temperature": row[7],
        }

    # ----- Knowledge and ontology -----
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

    # ----- execution records -----
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
            {"id": r[0], "goal": r[1], "boundary": r[2], "skill_report": json.loads(r[3]), "created_at": r[4]}
            for r in rows
        ]

    def load_judgements(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, goal, payload, diagnostics, created_at FROM judgements ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "goal": r[1],
                "decisions": json.loads(r[2]),
                "diagnostics": json.loads(r[3]),
                "created_at": r[4],
            }
            for r in rows
        ]

    # ----- Documents -----
    def save_document_record(self, metadata: Dict[str, Any]) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents(filename, format, status, sections, text_length, scenario, message, knowledge_base_id, mime_type, file_size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.get("filename", ""),
                    metadata.get("format", ""),
                    metadata.get("status", ""),
                    int(metadata.get("sections", 0)),
                    int(metadata.get("text_length", 0)),
                    metadata.get("scenario", ""),
                    metadata.get("message", ""),
                    metadata.get("knowledge_base_id"),
                    metadata.get("mime_type", ""),
                    int(metadata.get("file_size_bytes", 0)),
                ),
            )
        return int(cur.lastrowid)

    def load_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, filename, format, status, sections, text_length, scenario, message, knowledge_base_id, mime_type, file_size_bytes, created_at FROM documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "filename": r[1],
                "format": r[2],
                "status": r[3],
                "sections": r[4],
                "text_length": r[5],
                "scenario": r[6],
                "message": r[7],
                "knowledge_base_id": r[8],
                "mime_type": r[9],
                "file_size_bytes": r[10],
                "created_at": r[11],
            }
            for r in rows
        ]

    # ----- notes -----
    def add_knowledge_note(self, knowledge_id: str, note: str, tags: List[str]) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO knowledge_notes(knowledge_id, note, tags) VALUES (?, ?, ?)",
                (knowledge_id, note, json.dumps(tags, ensure_ascii=False)),
            )
        return int(cur.lastrowid)

    def list_knowledge_notes(self, knowledge_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, note, tags, created_at FROM knowledge_notes WHERE knowledge_id = ? ORDER BY id DESC",
                (knowledge_id,),
            ).fetchall()
        return [
            {"id": r[0], "note": r[1], "tags": json.loads(r[2]), "created_at": r[3]} for r in rows
        ]

    @staticmethod
    def parse_datetime(raw: str) -> datetime:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
