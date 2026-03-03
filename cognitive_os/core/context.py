from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class GoalContext:
    goal: str
    boundary: str = "global"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CognitiveFrame:
    rules: list
    knowledge_units: list
    ontology_entities: list
