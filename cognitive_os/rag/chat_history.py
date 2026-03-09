from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else data.get("timestamp", datetime.utcnow()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChatSession:
    session_id: str
    knowledge_base_id: Optional[int]
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> ChatMessage:
        message = ChatMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        return message

    def get_context(self, max_messages: int = 10) -> str:
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        context_parts = []
        for msg in recent:
            prefix = "用户" if msg.role == "user" else "助手"
            context_parts.append(f"{prefix}: {msg.content}")
        return "\n".join(context_parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "knowledge_base_id": self.knowledge_base_id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class ChatHistoryManager:
    def __init__(self, db_path: str = "./data/chat_history.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    knowledge_base_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON chat_messages(session_id, timestamp DESC)
            """)
            conn.commit()

    def create_session(self, session_id: str, knowledge_base_id: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> ChatSession:
        session = ChatSession(
            session_id=session_id,
            knowledge_base_id=knowledge_base_id,
            metadata=metadata or {},
        )

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (session_id, knowledge_base_id, metadata)
                VALUES (?, ?, ?)
                """,
                (session_id, knowledge_base_id, json.dumps(metadata or {})),
            )
            conn.commit()

        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            session = ChatSession(
                session_id=row["session_id"],
                knowledge_base_id=row["knowledge_base_id"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
                updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
                metadata=json.loads(row["metadata"] or "{}"),
            )

            cursor = conn.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            )
            for msg_row in cursor.fetchall():
                session.messages.append(ChatMessage(
                    role=msg_row["role"],
                    content=msg_row["content"],
                    timestamp=datetime.fromisoformat(msg_row["timestamp"]) if msg_row["timestamp"] else datetime.utcnow(),
                    metadata=json.loads(msg_row["metadata"] or "{}"),
                ))

        return session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        message = ChatMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, json.dumps(metadata or {})),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

        return message

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[ChatMessage]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (session_id, limit),
            )

            messages = []
            for row in reversed(cursor.fetchall()):
                messages.append(ChatMessage(
                    role=row["role"],
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else datetime.utcnow(),
                    metadata=json.loads(row["metadata"] or "{}"),
                ))

        return messages

    def get_history_context(self, session_id: str, max_messages: int = 10) -> str:
        messages = self.get_recent_messages(session_id, max_messages)
        context_parts = []
        for msg in messages:
            prefix = "用户" if msg.role == "user" else "助手"
            context_parts.append(f"{prefix}: {msg.content}")
        return "\n".join(context_parts)

    def delete_session(self, session_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            cursor = conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(self, knowledge_base_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if knowledge_base_id is not None:
                cursor = conn.execute(
                    """
                    SELECT session_id, knowledge_base_id, created_at, updated_at
                    FROM chat_sessions
                    WHERE knowledge_base_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (knowledge_base_id, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT session_id, knowledge_base_id, created_at, updated_at
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            return [dict(row) for row in cursor.fetchall()]

    def clear_old_sessions(self, days: int = 30) -> int:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM chat_sessions 
                WHERE updated_at < datetime('now', ?)
                """,
                (f"-{days} days",),
            )
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
