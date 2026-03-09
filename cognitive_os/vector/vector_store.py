from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(slots=True)
class VectorHit:
    id: str
    score: float
    metadata: Dict[str, Any]
    text: str


class EmbeddingModel:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vec
        for tok in tokens:
            idx = hash(tok) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class LocalVectorDB:
    def __init__(self, db_path: Path, table: str = "vector_knowledge") -> None:
        if isinstance(db_path, str):
            db_path = Path(db_path)
        self.db_path = db_path
        self.table = table
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = EmbeddingModel(dim=256)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def upsert(self, item_id: str, text: str, metadata: Dict[str, Any]) -> None:
        emb = self.embedder.embed(text)
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {self.table}(id, text, embedding, metadata) VALUES (?, ?, ?, ?)",
                (item_id, text, json.dumps(emb), json.dumps(metadata, ensure_ascii=False)),
            )


    def delete(self, item_id: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (item_id,))
        return int(cur.rowcount)

    def delete_by_document_id(self, document_id: int) -> int:
        removed = 0
        with self._connect() as conn:
            rows = conn.execute(f"SELECT id, metadata FROM {self.table}").fetchall()
            for row in rows:
                try:
                    meta = json.loads(row[1])
                except Exception:
                    continue
                if int(meta.get("document_id") or 0) == int(document_id):
                    conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (row[0],))
                    removed += 1
        return removed

    def search(self, query: str, top_k: int = 8) -> List[VectorHit]:
        q = self.embedder.embed(query)
        hits: List[VectorHit] = []
        with self._connect() as conn:
            rows = conn.execute(f"SELECT id, text, embedding, metadata FROM {self.table}").fetchall()
        for row in rows:
            emb = json.loads(row[2])
            score = sum(a * b for a, b in zip(q, emb))
            hits.append(VectorHit(id=row[0], score=score, text=row[1], metadata=json.loads(row[3])))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]


class KnowledgeWeightedRetriever:
    """Novel weighting: semantic similarity + confidence + source trust - conflict penalty."""

    SOURCE_WEIGHT = {"human_verified": 0.20, "private": 0.08, "public": 0.03}

    @classmethod
    def rerank(cls, hits: List[VectorHit]) -> List[VectorHit]:
        scored = []
        for hit in hits:
            confidence = float(hit.metadata.get("confidence", 0.5))
            source = str(hit.metadata.get("source", "public"))
            conflicts = int(hit.metadata.get("conflict_count", 0))
            boost = confidence * 0.25 + cls.SOURCE_WEIGHT.get(source, 0.01) - min(0.18, conflicts * 0.04)
            final = hit.score + boost
            scored.append(VectorHit(id=hit.id, score=final, text=hit.text, metadata=hit.metadata))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored
