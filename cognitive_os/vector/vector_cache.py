from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CachedVector:
    text_hash: str
    vector: List[float]
    model_name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_hash": self.text_hash,
            "vector": self.vector,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
            "metadata": self.metadata,
        }


class VectorCache:
    DEFAULT_TTL_DAYS = 30
    MAX_CACHE_SIZE = 100000

    def __init__(
        self,
        cache_dir: str = "./data/vector_cache",
        ttl_days: int = DEFAULT_TTL_DAYS,
        max_size: int = MAX_CACHE_SIZE,
    ):
        self._cache_dir = cache_dir
        self._ttl_days = ttl_days
        self._max_size = max_size
        self._conn: Optional[sqlite3.Connection] = None

        if cache_dir == ":memory:":
            self._db_path = ":memory:"
        else:
            self._cache_dir_path = Path(cache_dir)
            self._cache_dir_path.mkdir(parents=True, exist_ok=True)
            self._db_path = str(self._cache_dir_path / "vector_cache.db")

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:")
            return self._conn
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vector_cache (
                text_hash TEXT PRIMARY KEY,
                vector BLOB NOT NULL,
                model_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_model 
            ON vector_cache(model_name, last_accessed DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_access 
            ON vector_cache(access_count DESC)
        """)
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    @staticmethod
    def compute_hash(text: str) -> str:
        normalized = " ".join(text.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

    def get(self, text: str, model_name: str = "default") -> Optional[List[float]]:
        text_hash = self.compute_hash(text)

        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT vector, model_name FROM vector_cache 
            WHERE text_hash = ? AND model_name = ?
            """,
            (text_hash, model_name),
        )
        row = cursor.fetchone()

        if row:
            conn.execute(
                """
                UPDATE vector_cache 
                SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE text_hash = ?
                """,
                (text_hash,),
            )
            conn.commit()
            vector = json.loads(row["vector"])
            if self._db_path != ":memory:":
                conn.close()
            return vector

        if self._db_path != ":memory:":
            conn.close()
        return None

    def set(
        self,
        text: str,
        vector: List[float],
        model_name: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        text_hash = self.compute_hash(text)
        vector_json = json.dumps(vector)
        metadata_json = json.dumps(metadata or {})

        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO vector_cache 
            (text_hash, vector, model_name, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (text_hash, vector_json, model_name, metadata_json),
        )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

        self._check_size()

    def get_batch(
        self,
        texts: List[str],
        model_name: str,
    ) -> Tuple[Dict[int, List[float]], List[int]]:
        results: Dict[int, List[float]] = {}
        missing: List[int] = []

        for i, text in enumerate(texts):
            vector = self.get(text, model_name)
            if vector is not None:
                results[i] = vector
            else:
                missing.append(i)

        return results, missing

    def set_batch(
        self,
        texts: List[str],
        vectors: List[List[float]],
        model_name: str = "default",
    ) -> None:
        conn = self._get_connection()
        for text, vector in zip(texts, vectors):
            text_hash = self.compute_hash(text)
            vector_json = json.dumps(vector)
            conn.execute(
                """
                INSERT OR REPLACE INTO vector_cache 
                (text_hash, vector, model_name)
                VALUES (?, ?, ?)
                """,
                (text_hash, vector_json, model_name),
            )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

        self._check_size()

    def _check_size(self) -> None:
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM vector_cache")
        count = cursor.fetchone()[0]

        if count > self._max_size:
            excess = count - self._max_size + int(self._max_size * 0.1)
            conn.execute(
                """
                DELETE FROM vector_cache 
                WHERE text_hash IN (
                    SELECT text_hash FROM vector_cache 
                    ORDER BY access_count ASC, last_accessed ASC 
                    LIMIT ?
                )
                """,
                (excess,),
            )
            conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def clear_expired(self) -> int:
        cutoff = datetime.utcnow() - timedelta(days=self._ttl_days)

        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM vector_cache WHERE created_at < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
        result = cursor.rowcount
        if self._db_path != ":memory:":
            conn.close()
        return result

    def clear_all(self) -> None:
        conn = self._get_connection()
        conn.execute("DELETE FROM vector_cache")
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("SELECT COUNT(*) as count FROM vector_cache")
        total_count = cursor.fetchone()["count"]

        cursor = conn.execute(
            """
            SELECT model_name, COUNT(*) as count 
            FROM vector_cache 
            GROUP BY model_name
            """
        )
        by_model = {row["model_name"]: row["count"] for row in cursor.fetchall()}

        cursor = conn.execute(
            "SELECT SUM(access_count) as total FROM vector_cache"
        )
        total_accesses = cursor.fetchone()["total"] or 0

        if self._db_path != ":memory:":
            conn.close()

        return {
            "total_cached": total_count,
            "by_model": by_model,
            "total_accesses": total_accesses,
            "max_size": self._max_size,
            "ttl_days": self._ttl_days,
        }

    def warmup(
        self,
        texts: List[str],
        embed_fn,
        model_name: str,
        batch_size: int = 100,
    ) -> int:
        cached = 0
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            existing, missing = self.get_batch(batch, model_name)

            if missing:
                to_embed = [batch[j] for j in missing]
                vectors = embed_fn(to_embed)
                self.set_batch(to_embed, vectors, model_name)
                cached += len(missing)

        return cached
