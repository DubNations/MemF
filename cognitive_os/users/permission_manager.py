from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class Permission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SHARE = "share"
    ADMIN = "admin"


class ResourceType(Enum):
    KNOWLEDGE_BASE = "knowledge_base"
    DOCUMENT = "document"
    RULE = "rule"
    KNOWLEDGE_UNIT = "knowledge_unit"
    SESSION = "session"


@dataclass
class ResourcePermission:
    resource_type: ResourceType
    resource_id: str
    user_id: str
    permissions: Set[Permission] = field(default_factory=set)
    granted_at: datetime = field(default_factory=datetime.utcnow)
    granted_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "permissions": [p.value for p in self.permissions],
            "granted_at": self.granted_at.isoformat(),
            "granted_by": self.granted_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourcePermission":
        return cls(
            resource_type=ResourceType(data["resource_type"]),
            resource_id=data["resource_id"],
            user_id=data["user_id"],
            permissions={Permission(p) for p in data.get("permissions", [])},
            granted_at=datetime.fromisoformat(data["granted_at"]) if isinstance(data.get("granted_at"), str) else data.get("granted_at", datetime.utcnow()),
            granted_by=data.get("granted_by"),
        )


class PermissionManager:
    ROLE_PERMISSIONS: Dict[str, Set[Permission]] = {
        "admin": {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.SHARE, Permission.ADMIN},
        "editor": {Permission.READ, Permission.WRITE, Permission.SHARE},
        "viewer": {Permission.READ},
        "guest": {Permission.READ},
    }

    def __init__(self, db_path: str = "./data/users.db"):
        self._db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS resource_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    granted_by TEXT,
                    UNIQUE(resource_type, resource_id, user_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_permissions_resource 
                ON resource_permissions(resource_type, resource_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_permissions_user 
                ON resource_permissions(user_id)
            """)
            conn.commit()

    def grant_permission(
        self,
        resource_type: ResourceType,
        resource_id: str,
        user_id: str,
        permissions: Set[Permission],
        granted_by: Optional[str] = None,
    ) -> bool:
        perms_str = ",".join(p.value for p in permissions)

        with sqlite3.connect(self._db_path) as conn:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO resource_permissions 
                    (resource_type, resource_id, user_id, permissions, granted_by)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (resource_type.value, resource_id, user_id, perms_str, granted_by),
                )
                conn.commit()
                return True
            except Exception:
                return False

    def revoke_permission(
        self,
        resource_type: ResourceType,
        resource_id: str,
        user_id: str,
    ) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM resource_permissions 
                WHERE resource_type = ? AND resource_id = ? AND user_id = ?
                """,
                (resource_type.value, resource_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_user_permissions(
        self,
        resource_type: ResourceType,
        resource_id: str,
        user_id: str,
        user_role: str = "viewer",
    ) -> Set[Permission]:
        role_perms = self.ROLE_PERMISSIONS.get(user_role, {Permission.READ})

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT permissions FROM resource_permissions 
                WHERE resource_type = ? AND resource_id = ? AND user_id = ?
                """,
                (resource_type.value, resource_id, user_id),
            )
            row = cursor.fetchone()

            if row:
                resource_perms = {Permission(p) for p in row["permissions"].split(",") if p}
                return role_perms | resource_perms

        return role_perms

    def check_permission(
        self,
        resource_type: ResourceType,
        resource_id: str,
        user_id: str,
        permission: Permission,
        user_role: str = "viewer",
    ) -> bool:
        perms = self.get_user_permissions(resource_type, resource_id, user_id, user_role)
        return permission in perms

    def list_user_resources(
        self,
        user_id: str,
        resource_type: Optional[ResourceType] = None,
    ) -> List[Dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if resource_type:
                cursor = conn.execute(
                    """
                    SELECT * FROM resource_permissions 
                    WHERE user_id = ? AND resource_type = ?
                    """,
                    (user_id, resource_type.value),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM resource_permissions WHERE user_id = ?",
                    (user_id,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def list_resource_users(
        self,
        resource_type: ResourceType,
        resource_id: str,
    ) -> List[Dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT user_id, permissions, granted_at, granted_by 
                FROM resource_permissions 
                WHERE resource_type = ? AND resource_id = ?
                """,
                (resource_type.value, resource_id),
            )
            return [dict(row) for row in cursor.fetchall()]

    def share_resource(
        self,
        resource_type: ResourceType,
        resource_id: str,
        target_user_id: str,
        permissions: Set[Permission],
        granted_by: str,
    ) -> bool:
        return self.grant_permission(resource_type, resource_id, target_user_id, permissions, granted_by)

    def transfer_ownership(
        self,
        resource_type: ResourceType,
        resource_id: str,
        new_owner_id: str,
        current_owner_id: str,
    ) -> bool:
        new_perms = self.ROLE_PERMISSIONS["admin"]
        return self.grant_permission(
            resource_type, resource_id, new_owner_id, new_perms, current_owner_id
        )


def check_permission_decorator(permission: Permission, resource_type: ResourceType):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            user_id = kwargs.get("user_id") or (args[0] if args else None)
            resource_id = kwargs.get("resource_id") or kwargs.get("id") or (args[1] if len(args) > 1 else None)
            user_role = kwargs.get("user_role", "viewer")

            if not user_id or not resource_id:
                raise PermissionError("Missing user_id or resource_id for permission check")

            pm = PermissionManager()
            if not pm.check_permission(resource_type, resource_id, user_id, permission, user_role):
                raise PermissionError(
                    f"User {user_id} does not have {permission.value} permission on {resource_type.value}:{resource_id}"
                )

            return func(self, *args, **kwargs)

        return wrapper
    return decorator
