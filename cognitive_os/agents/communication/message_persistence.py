from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cognitive_os.agents.communication.message_queue import Message


@dataclass
class PersistedMessage:
    id: str
    sender: str
    content: Any
    timestamp: datetime
    processed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "processed": self.processed,
            "metadata": self.metadata,
        }


class MessagePersistence:
    def __init__(self, db_path: str = "./data/messages.db"):
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
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
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT 0,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sender ON messages(sender)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)
        """)
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def save_message(self, message: Message) -> None:
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO messages (id, sender, content, timestamp, processed, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.sender,
                json.dumps(message.content) if not isinstance(message.content, str) else message.content,
                message.timestamp.isoformat(),
                False,
                json.dumps(message.metadata),
            ),
        )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def get_message(self, message_id: str) -> Optional[PersistedMessage]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,),
        )
        row = cursor.fetchone()
        if self._db_path != ":memory:":
            conn.close()
        
        if not row:
                return None
        
        return PersistedMessage(
            id=row["id"],
            sender=row["sender"],
            content=json.loads(row["content"]) if row["content"] else {},
            timestamp=datetime.fromisoformat(row["timestamp"]),
            processed=bool(row["processed"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def get_messages_by_sender(
        self,
        sender: str,
        limit: int = 100,
    ) -> List[PersistedMessage]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT * FROM messages 
            WHERE sender = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (sender, limit),
        )
        rows = cursor.fetchall()
        if self._db_path != ":memory:":
            conn.close()
        
        return [
            PersistedMessage(
                id=row["id"],
                sender=row["sender"],
                content=json.loads(row["content"]) if row["content"] else {},
                timestamp=datetime.fromisoformat(row["timestamp"]),
                processed=bool(row["processed"]),
                metadata=json.loads(row["metadata"] or "{}"),
            )
            for row in rows
        ]

    def get_unprocessed_messages(self, limit: int = 100) -> List[PersistedMessage]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT * FROM messages 
            WHERE processed = 0 
            ORDER BY timestamp ASC 
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        if self._db_path != ":memory:":
            conn.close()
        
        return [
            PersistedMessage(
                id=row["id"],
                sender=row["sender"],
                content=json.loads(row["content"]) if row["content"] else {},
                timestamp=datetime.fromisoformat(row["timestamp"]),
                processed=False,
                metadata=json.loads(row["metadata"] or "{}"),
            )
            for row in rows
        ]

    def mark_processed(self, message_id: str) -> None:
        conn = self._get_connection()
        conn.execute(
            "UPDATE messages SET processed = 1 WHERE id = ?",
            (message_id,),
        )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def delete_message(self, message_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM messages WHERE id = ?",
            (message_id,),
        )
        conn.commit()
        result = cursor.rowcount > 0
        if self._db_path != ":memory:":
            conn.close()
        return result

    def get_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        
        cursor = conn.execute("SELECT COUNT(*) FROM messages")
        total = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM messages WHERE processed = 0")
        unprocessed = cursor.fetchone()[0]
        
        cursor = conn.execute(
            "SELECT sender, COUNT(*) FROM messages GROUP BY sender"
        )
        by_sender = {row[0]: row[1] for row in cursor.fetchall()}
        
        if self._db_path != ":memory:":
            conn.close()
        
        return {
            "total_messages": total,
            "unprocessed": unprocessed,
            "by_sender": by_sender,
        }
