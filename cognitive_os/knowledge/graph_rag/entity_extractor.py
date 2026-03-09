from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Entity:
    id: str
    name: str
    entity_type: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "properties": self.properties,
            "confidence": self.confidence,
        }


@dataclass
class Relation:
    id: str
    source_id: str
    target_id: str
    relation_type: str
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "description": self.description,
            "properties": self.properties,
            "confidence": self.confidence,
        }


class EntityExtractor:
    ENTITY_PATTERNS = {
        "person": [
            r"([A-Z][a-z]+\s+[A-Z][a-z]+)",
            r"(Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+)",
        ],
        "organization": [
            r"([A-Z][A-Za-z]+(?:\s+(?:Inc|Corp|Company|LLC|Ltd|Group|Institute|University|College))?)",
            r"(?:The\s+)?[A-Z][A-Za-z\s]+(?:Team|Department|Division|Agency))",
        ],
        "location": [
            r"([A-Z][a-z]+(?:\s+[a-z]+)?,\s*[A-Z]{2})",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:City|State|Country|Region))",
        ],
        "concept": [
            r"([A-Z][a-z]+(?:\s+[a-z]+)?\s+(?:Theory|Principle|Law|Method|Algorithm))",
        ],
        "event": [
            r"([A-Z][a-z]+(?:\s+[a-z]+)?\s+(?:Conference|Summit|Meeting|Election|War))",
            r"(?:in\s+)(\d{4})",
        ],
        "product": [
            r"([A-Z][A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)*\s+(?:Pro|Max|Plus|Lite))?",
            r"(?:iPhone|Android|Windows|MacOS|Linux)",
        ],
    }
    
    RELATION_PATTERNS = {
        "works_for": [
            r"(\w+)\s+works\s+for\s+(\w+)",
            r"(\w+)\s+(?:is|are)\s+(?:an?\s+)?(?:employee|staff|worker)\s+at\s+(\w+)",
        ],
        "located_in": [
            r"(\w+)\s+(?:is\s+)?located\s+in\s+(\w+)",
            r"(\w+)\s+(?:is\s+)?based\s+in\s+(\w+)",
        ],
        "founded_by": [
            r"(\w+)\s+(?:was\s+)?founded\s+by\s+(\w+)",
            r"(\w+)\s+(?:was\s+)?created\s+by\s+(\w+)",
        ],
        "part_of": [
            r"(\w+)\s+(?:is\s+)?(?:a\s+)?part\s+of\s+(\w+)",
            r"(\w+)\s+belongs\s+to\s+(\w+)",
        ],
        "related_to": [
            r"(\w+)\s+(?:is\s+)?related\s+to\s+(\w+)",
            r"(\w+)\s+(?:has\s+)?(?:a\s+)?relationship\s+with\s+(\w+)",
        ],
    }

    def __init__(self, llm_client=None):
        self._llm_client = llm_client
        self._entity_cache: Dict[str, Entity] = {}
        self._relation_cache: Dict[str, Relation] = {}

    def extract_entities(self, text: str) -> Tuple[List[Entity], List[Relation]]:
        entities = self._extract_by_patterns(text)
        relations = self._extract_relations(text, entities)
        
        if self._llm_client:
            llm_entities, llm_relations = self._extract_by_llm(text)
            entities.extend(llm_entities)
            relations.extend(llm_relations)
        
        entities = self._deduplicate_entities(entities)
        relations = self._deduplicate_relations(relations)
        
        for e in entities:
            self._entity_cache[e.id] = e
        for r in relations:
            self._relation_cache[r.id] = r
        
        return entities, relations

    def _extract_by_patterns(self, text: str) -> List[Entity]:
        entities = []
        seen = set()
        
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    name = match.group(0).strip()
                    if name.lower() not in seen:
                        entity = Entity(
                            id=f"{entity_type}_{len(entities)}",
                            name=name,
                            entity_type=entity_type,
                            description=f"Extracted from text: {text[max(0, match.start()-20):match.end()+20]}",
                            confidence=0.7,
                        )
                        entities.append(entity)
                        seen.add(name.lower())
        
        return entities

    def _extract_relations(
        self, text: str, entities: List[Entity]
    ) -> List[Relation]:
        relations = []
        entity_map = {e.name.lower(): e for e in entities}
        
        for rel_type, patterns in self.RELATION_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    source_name = match.group(1).strip()
                    target_name = match.group(2).strip()
                    
                    source = entity_map.get(source_name.lower())
                    target = entity_map.get(target_name.lower())
                    
                    if source and target:
                        relation = Relation(
                            id=f"{rel_type}_{len(relations)}",
                            source_id=source.id,
                            target_id=target.id,
                            relation_type=rel_type,
                            description=f"Extracted: {match.group(0)}",
                            confidence=0.7,
                        )
                        relations.append(relation)
        
        return relations

    def _extract_by_llm(self, text: str) -> Tuple[List[Entity], List[Relation]]:
        if not self._llm_client:
            return [], []
        
        entities = []
        relations = []
        
        prompt = f"""Extract entities and relations from the following text. Return JSON format:
{{
    "entities": [
        {{"name": "Entity Name", "type": "person|organization|location|concept|event|product", "description": "Brief description"}}
    ],
    "relations": [
        {{"source": "Entity1", "target": "Entity2", "type": "works_for|located_in|founded_by|part_of|related_to"}}
    ]
}}

Text:
{text[:2000]}
"""
        try:
            response = self._llm_client.chat(prompt)
            data = json.loads(response)
            
            for i, e in enumerate(data.get("entities", [])):
                entity = Entity(
                    id=f"llm_entity_{i}",
                    name=e.get("name", ""),
                    entity_type=e.get("type", "concept"),
                    description=e.get("description", ""),
                    confidence=0.9,
                )
                entities.append(entity)
            
            for i, r in enumerate(data.get("relations", [])):
                source = next((e for e in entities if e.name == r.get("source")), None)
                target = next((e for e in entities if e.name == r.get("target")), None)
                
                if source and target:
                    relation = Relation(
                        id=f"llm_rel_{i}",
                        source_id=source.id,
                        target_id=target.id,
                        relation_type=r.get("type", "related_to"),
                        confidence=0.9,
                    )
                    relations.append(relation)
        except Exception:
            pass
        
        return entities, relations

    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        seen = {}
        for e in entities:
            key = f"{e.entity_type}_{e.name.lower()}"
            if key not in seen or e.confidence > seen[key].confidence:
                seen[key] = e
        return list(seen.values())

    def _deduplicate_relations(self, relations: List[Relation]) -> List[Relation]:
        seen = {}
        for r in relations:
            key = f"{r.source_id}_{r.relation_type}_{r.target_id}"
            if key not in seen or r.confidence > seen[key].confidence:
                seen[key] = r
        return list(seen.values())

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entity_cache.get(entity_id)

    def get_all_entities(self) -> List[Entity]:
        return list(self._entity_cache.values())

    def get_all_relations(self) -> List[Relation]:
        return list(self._relation_cache.values())
