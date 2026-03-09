from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CustomCommand:
    name: str
    description: str
    template: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomCommand":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            template=data.get("template", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow()),
            created_by=data.get("created_by"),
            is_active=data.get("is_active", True),
        )


class CustomCommandManager:
    def __init__(self, db_path: str = "./data/custom_commands.db"):
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._handlers: Dict[str, Callable] = {}
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
            CREATE TABLE IF NOT EXISTS custom_commands (
                name TEXT PRIMARY KEY,
                description TEXT,
                template TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def create_command(
        self,
        name: str,
        description: str = "",
        template: str = "",
        created_by: Optional[str] = None,
    ) -> CustomCommand:
        command = CustomCommand(
            name=name.lower(),
            description=description,
            template=template,
            created_by=created_by,
        )

        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO custom_commands 
            (name, description, template, created_by, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (command.name, command.description, command.template, command.created_by),
        )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

        return command

    def get_command(self, name: str) -> Optional[CustomCommand]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM custom_commands WHERE name = ? AND is_active = 1",
            (name.lower(),),
        )
        row = cursor.fetchone()
        if self._db_path != ":memory:":
            conn.close()
        if not row:
            return None
        return CustomCommand.from_dict(dict(row))

    def list_commands(self) -> List[CustomCommand]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM custom_commands WHERE is_active = 1 ORDER BY created_at DESC"
        )
        results = [CustomCommand.from_dict(dict(row)) for row in cursor.fetchall()]
        if self._db_path != ":memory:":
            conn.close()
        return results

    def delete_command(self, name: str) -> bool:
        conn = self._get_connection()
        cursor = conn.execute(
            "UPDATE custom_commands SET is_active = 0 WHERE name = ?",
            (name.lower(),),
        )
        conn.commit()
        result = cursor.rowcount > 0
        if self._db_path != ":memory:":
            conn.close()
        return result

    def register_handler(self, name: str, handler: Callable) -> None:
        self._handlers[name.lower()] = handler

    def get_handler(self, name: str) -> Optional[Callable]:
        return self._handlers.get(name.lower())

    def expand_template(self, name: str, args: List[str], context: Dict[str, Any]) -> str:
        command = self.get_command(name)
        if not command:
            return ""

        template = command.template
        for i, arg in enumerate(args):
            template = template.replace(f"{{{{arg{i}}}}}", arg)
            template = template.replace(f"{{arg{i}}}", arg)

        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                template = template.replace(f"{{{{{key}}}}}", str(value))

        return template
