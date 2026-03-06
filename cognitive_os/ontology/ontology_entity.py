from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class OntologyRelation:
    type: str
    target: str


@dataclass(slots=True)
class OntologyEntity:
    name: str
    type: str = "concept"
    attributes: Dict[str, Any] = field(default_factory=dict)
    relations: List[OntologyRelation] = field(default_factory=list)


@dataclass(slots=True)
class KnowledgeUnit:
    id: str
    knowledge_type: str
    content: Any
    source: str
    confidence: float
    valid_boundary: str
    invalid_boundary: str = ""
    conflict_ids: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "KnowledgeUnit":
        return cls(
            id=payload["id"],
            knowledge_type=payload["knowledge_type"],
            content=payload["content"],
            source=payload["source"],
            confidence=float(payload.get("confidence", 0.0)),
            valid_boundary=payload.get("valid_boundary", "global"),
            invalid_boundary=payload.get("invalid_boundary", ""),
            conflict_ids=list(payload.get("conflict_ids", [])),
        )
