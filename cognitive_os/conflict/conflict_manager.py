from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from cognitive_os.ontology.ontology_engine import KnowledgeGraph
from cognitive_os.ontology.ontology_entity import KnowledgeUnit


@dataclass(slots=True)
class ConflictIssue:
    type: str
    message: str
    knowledge_ids: List[str]
    topic: str = ""
    reason_code: str = ""


class ConflictManager:
    low_confidence_threshold = 0.4

    @staticmethod
    def check(knowledge_graph: KnowledgeGraph) -> List[ConflictIssue]:
        issues: List[ConflictIssue] = []
        topic_polarity: Dict[str, Dict[str, List[str]]] = {}

        for unit in knowledge_graph.knowledge_units.values():
            if unit.confidence < ConflictManager.low_confidence_threshold:
                issues.append(
                    ConflictIssue(
                        type="LOW_CONFIDENCE",
                        message=f"Knowledge {unit.id} confidence is below threshold",
                        knowledge_ids=[unit.id],
                        reason_code="CONFIDENCE_BELOW_THRESHOLD",
                    )
                )
            if not unit.content:
                issues.append(
                    ConflictIssue(
                        type="MISSING",
                        message=f"Knowledge {unit.id} content is missing",
                        knowledge_ids=[unit.id],
                        reason_code="MISSING_CONTENT",
                    )
                )

            if isinstance(unit.content, dict):
                topic = str(unit.content.get("topic", "")).strip()
                polarity = str(unit.content.get("polarity", "")).strip().lower()
                if topic and polarity in {"pro", "con"}:
                    bucket = topic_polarity.setdefault(topic, {"pro": [], "con": []})
                    bucket[polarity].append(unit.id)

        for topic, sides in topic_polarity.items():
            if sides["pro"] and sides["con"]:
                issues.append(
                    ConflictIssue(
                        type="CONTRADICTION",
                        message=f"Contradictory evidence on topic={topic}",
                        knowledge_ids=sides["pro"] + sides["con"],
                        topic=topic,
                        reason_code="TOPIC_POLARITY_CONFLICT",
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
