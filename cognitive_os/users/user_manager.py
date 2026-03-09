from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class UserRole(Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"

    def permissions(self) -> List[str]:
        perms = {
            UserRole.ADMIN: ["read", "write", "delete", "share", "admin"],
            UserRole.EDITOR: ["read", "write", "share"],
            UserRole.VIEWER: ["read"],
            UserRole.GUEST: ["read"],
        }
        return perms.get(self, ["read"])


@dataclass
class User:
    id: str
    email: str
    name: str
    role: UserRole = UserRole.VIEWER
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role.value,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            id=data["id"],
            email=data["email"],
            name=data.get("name", ""),
            role=UserRole(data.get("role", "viewer")),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow()),
            last_login=datetime.fromisoformat(data["last_login"]) if data.get("last_login") else None,
            is_active=data.get("is_active", True),
            metadata=data.get("metadata", {}),
        )


@dataclass
class APIKey:
    key_hash: str
    user_id: str
    name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True

    @staticmethod
    def generate_key() -> str:
        return f"ck_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_hash": self.key_hash,
            "user_id": self.user_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active,
        }


class UserManager:
    def __init__(self, db_path: str = "./data/users.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    role TEXT DEFAULT 'viewer',
                    password_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    last_used TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")
            conn.commit()

    def create_user(
        self,
        email: str,
        name: str,
        role: UserRole = UserRole.VIEWER,
        password: Optional[str] = None,
    ) -> User:
        user_id = f"user_{secrets.token_urlsafe(8)}"
        password_hash = self._hash_password(password) if password else None

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, name, role, password_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, name, role.value, password_hash, "{}"),
            )
            conn.commit()

        return User(id=user_id, email=email, name=name, role=role)

    def get_user(self, user_id: str) -> Optional[User]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return User.from_dict(dict(row))

    def get_user_by_email(self, email: str) -> Optional[User]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if not row:
                return None
            return User.from_dict(dict(row))

    def update_user(self, user_id: str, **kwargs: Any) -> bool:
        allowed_fields = {"name", "role", "is_active", "metadata"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, user_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM api_keys WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_users(self, limit: int = 50, offset: int = 0) -> List[User]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return [User.from_dict(dict(row)) for row in cursor.fetchall()]

    def verify_password(self, email: str, password: str) -> Optional[User]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users WHERE email = ? AND is_active = 1",
                (email,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            stored_hash = row["password_hash"]
            if not stored_hash:
                return None

            if not self._verify_password_hash(password, stored_hash):
                return None

            user = User.from_dict(dict(row))
            conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user.id,),
            )
            conn.commit()
            return user

    def create_api_key(self, user_id: str, name: str = "default", expires_days: Optional[int] = None) -> str:
        raw_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(raw_key)

        expires_at = None
        if expires_days:
            from datetime import timedelta
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO api_keys (key_hash, user_id, name, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (key_hash, user_id, name, expires_at.isoformat() if expires_at else None),
            )
            conn.commit()

        return raw_key

    def verify_api_key(self, raw_key: str) -> Optional[User]:
        key_hash = APIKey.hash_key(raw_key)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT ak.*, u.* FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
                WHERE ak.key_hash = ? AND ak.is_active = 1 AND u.is_active = 1
                """,
                (key_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            expires_at = row["expires_at"]
            if expires_at:
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    return None

            conn.execute(
                "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE key_hash = ?",
                (key_hash,),
            )
            conn.commit()

            return User.from_dict({
                "id": row["user_id"],
                "email": row["email"],
                "name": row["name"],
                "role": row["role"],
                "created_at": row["created_at"],
                "last_login": row["last_login"],
                "is_active": bool(row["is_active"]),
                "metadata": json.loads(row["metadata"] or "{}"),
            })

    def revoke_api_key(self, key_hash: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET is_active = 0 WHERE key_hash = ?",
                (key_hash,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT name, created_at, expires_at, last_used, is_active
                FROM api_keys WHERE user_id = ? ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_session(self, user_id: str, expires_hours: int = 24) -> str:
        session_token = secrets.token_urlsafe(32)
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (session_token, user_id, expires_at)
                VALUES (?, ?, ?)
                """,
                (session_token, user_id, expires_at.isoformat()),
            )
            conn.commit()

        return session_token

    def verify_session(self, session_token: str) -> Optional[User]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT s.user_id, u.* FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = ? AND s.expires_at > CURRENT_TIMESTAMP AND u.is_active = 1
                """,
                (session_token,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return User.from_dict({
                "id": row["user_id"],
                "email": row["email"],
                "name": row["name"],
                "role": row["role"],
                "created_at": row["created_at"],
                "last_login": row["last_login"],
                "is_active": bool(row["is_active"]),
                "metadata": json.loads(row["metadata"] or "{}"),
            })

    def revoke_session(self, session_token: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM user_sessions WHERE session_token = ?",
                (session_token,),
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return f"{salt}:{key.hex()}"

    @staticmethod
    def _verify_password_hash(password: str, stored_hash: str) -> bool:
        try:
            salt, key_hex = stored_hash.split(":")
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
            return secrets.compare_digest(key.hex(), key_hex)
        except Exception:
            return False
