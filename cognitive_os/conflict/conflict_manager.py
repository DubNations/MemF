from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from cognitive_os.ontology.ontology_engine import KnowledgeGraph
from cognitive_os.ontology.ontology_entity import KnowledgeUnit


@dataclass(slots=True)
class ConflictIssue:
    type: str
    message: str
    knowledge_ids: List[str]


class ConflictManager:
    low_confidence_threshold = 0.4

    @staticmethod
    def check(knowledge_graph: KnowledgeGraph) -> List[ConflictIssue]:
        issues: List[ConflictIssue] = []
        for unit in knowledge_graph.knowledge_units.values():
            if unit.confidence < ConflictManager.low_confidence_threshold:
                issues.append(
                    ConflictIssue(
                        type="LOW_CONFIDENCE",
                        message=f"Knowledge {unit.id} confidence is below threshold",
                        knowledge_ids=[unit.id],
                    )
                )
            if not unit.content:
                issues.append(
                    ConflictIssue(
                        type="MISSING",
                        message=f"Knowledge {unit.id} content is missing",
                        knowledge_ids=[unit.id],
                    )
                )
        return issues

    @staticmethod
    def resolve_conflict(k1: KnowledgeUnit, k2: KnowledgeUnit) -> Optional[KnowledgeUnit]:
        if k1.source == "human_verified" and k2.source != "human_verified":
            return k1
        if k1.confidence > k2.confidence:
            return k1
        return None
