from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(slots=True)
class Rule:
    id: str
    scope: str
    condition: str
    action_constraint: str
    priority: int
    applicable_boundary: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Rule":
        return cls(
            id=payload["id"],
            scope=payload["scope"],
            condition=payload["condition"],
            action_constraint=payload["action_constraint"],
            priority=int(payload.get("priority", 1)),
            applicable_boundary=payload.get("applicable_boundary", "global"),
        )
