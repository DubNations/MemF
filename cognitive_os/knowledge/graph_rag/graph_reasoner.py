from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from cognitive_os.knowledge.graph_rag.entity_extractor import Entity, Relation
from cognitive_os.knowledge.graph_rag.graph_builder import GraphBuilder


class GraphReasoner:
    def __init__(self, graph_builder: GraphBuilder, llm_client=None):
        self._graph_builder = graph_builder
        self._llm_client = llm_client

    def reason(
        self,
        query: str,
        entities: Optional[List[Entity]] = None,
        relations: Optional[List[Relation]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not entities:
            entities = self._graph_builder.search_entities(query)
        
        if not relations:
            relations = self._graph_builder.get_relations_for_entity(entities[0].id) if entities else None
        
        result_entities = []
        result_relations = []
        
        if self._llm_client:
            reasoning = self._llm_reason(query, entities, relations)
            result_entities.extend(reasoning.get("additional_entities", []))
            result_relations.extend(reasoning.get("additional_relations", []))
        
        return result_entities, result_relations

    def _llm_reason(
        self,
        query: str,
        entities: List[Entity],
        relations: List[Relation],
    ) -> Tuple[List[Entity], List[Relation]]:
        prompt = f"""Based on the knowledge graph entities and relations, provide additional insights.

Current entities: {[e.name for e in entities]}
Current relations: {[r.source_id} --[{r.relation_type}]--> {[r.target_id} for r in relations]]

Query: {query}

Provide:
1. Additional entities that might be relevant
2. Additional relations that might provide deeper context
3. Any contradictions or inconsistencies

Format your response as JSON with:
{{
    "additional_entities": [...],
    "additional_relations": [...],
    "reasoning": "Brief explanation of the additional insights"
}}
"""
        try:
            response = self._llm_client.chat(prompt)
            data = json.loads(response)
            
            additional_entities = []
            for e in data.get("additional_entities", []):
                entity = Entity(
                    id=f"reason_entity_{len(additional_entities)}",
                    name=e.get("name", ""),
                    entity_type=e.get("type", "concept"),
                    description=e.get("description", ""),
                    confidence=0.9,
                )
                additional_entities.append(entity)
            
            additional_relations = []
            for r in data.get("additional_relations", []):
                relation = Relation(
                    id=f"reason_rel_{len(additional_relations)}",
                    source_id=r.get("source", ""),
                    target_id=r.get("target", ""),
                    relation_type=r.get("type", "related_to"),
                    description=r.get("description", ""),
                    confidence=0.9,
                )
                additional_relations.append(relation)
            
            result_entities.extend(additional_entities)
            result_relations.extend(additional_relations)
        except Exception:
            pass
        
        return result_entities, result_relations

    def get_entity_context(self, entity: Entity, context: Dict[str, Any]) -> str:
        relations = self._graph_builder.get_relations_for_entity(entity.id)
        context_parts = []
        for r in relations:
            source = self._graph_builder.get_entity(r.source_id)
            target = self._graph_builder.get_entity(r.target_id)
            if source and target:
                context_parts.append({
                "relation": r.relation_type,
                "source": source.name,
                "target": target.name,
                "description": r.description,
            })
        
        related = self._graph_builder.get_related_entities(entity.id, max_depth=2)
        for e in related:
            context_parts.append({
                "name": e.name,
                "type": e.entity_type,
                "description": e.description,
            })
        
        return context_parts
