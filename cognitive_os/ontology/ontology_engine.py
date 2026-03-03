from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from cognitive_os.core.context import CognitiveFrame
from cognitive_os.ontology.ontology_entity import KnowledgeUnit, OntologyEntity


@dataclass(slots=True)
class KnowledgeGraph:
    entities: Dict[str, OntologyEntity] = field(default_factory=dict)
    knowledge_units: Dict[str, KnowledgeUnit] = field(default_factory=dict)

    def update(self, new_units: List[KnowledgeUnit]) -> None:
        for unit in new_units:
            self.knowledge_units[unit.id] = unit


class OntologyEngine:
    @staticmethod
    def assemble(frame: CognitiveFrame) -> KnowledgeGraph:
        entity_map = {entity.name: entity for entity in frame.ontology_entities}
        ku_map = {unit.id: unit for unit in frame.knowledge_units}
        return KnowledgeGraph(entities=entity_map, knowledge_units=ku_map)
