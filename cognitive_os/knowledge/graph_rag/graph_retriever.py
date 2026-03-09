from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from cognitive_os.knowledge.graph_rag.entity_extractor import Entity, Relation
from cognitive_os.knowledge.graph_rag.graph_builder import GraphBuilder


class GraphRetriever:
    def __init__(self, graph_builder: GraphBuilder, vector_store=None):
        self._graph_builder = graph_builder
        self._vector_store = vector_store

    def retrieve_by_entity(
        self,
        query: str,
        top_k: int = 5,
    ) -> Tuple[List[Dict[str, Any]], List[Entity]]:
        entities = self._graph_builder.search_entities(query, limit=top_k)
        
        all_relations = []
        for entity in entities:
            relations = self._graph_builder.get_relations_for_entity(entity.id)
            all_relations.extend(relations)
        
        return [
            {
                "entity": e.to_dict(),
                "relations": [r.to_dict() for r in relations],
            }
            for e in entities
        ], all_relations

 []

    def retrieve_by_relation(
        self,
        source_entity: str,
        relation_type: str,
        max_depth: int = 2,
    ) -> Tuple[List[Dict[str, Any]], List[Entity]]:
        source = self._graph_builder.get_entity_by_name(source_entity)
        if not source:
            return [], []
        
        related = self._graph_builder.get_related_entities(
            source.id, relation_type, max_depth
        )
        
        return [
            {
                "source": source.to_dict(),
                "related_entities": [e.to_dict() for e in related],
            }
        ], related

    def retrieve_subgraph(
        self,
        query: str,
        max_entities: int = 10,
    ) -> Dict[str, Any]:
        entities = self._graph_builder.search_entities(query, limit=max_entities)
        
        graph_data = {
            "entities": {},
            "relations": {},
        }
        
        for entity in entities:
            graph_data["entities"][entity.id] = entity.to_dict()
            relations = self._graph_builder.get_relations_for_entity(entity.id)
            for r in relations:
                graph_data["relations"][r.id] = r.to_dict()
        
        return graph_data

    def hybrid_retrieve(
        self,
        query: str,
        vector_top_k: int = 5,
        graph_top_k: int = 5,
    ) -> Dict[str, Any]:
        results = {}
        
        if self._vector_store:
            vector_results = self._vector_store.search(query, top_k=vector_top_k)
            results["vector_results"] = vector_results
        
        graph_results = self.retrieve_subgraph(query, graph_top_k)
        results["graph_results"] = graph_results
        
        entities = self._graph_builder.search_entities(query, limit=graph_top_k)
        results["entities"] = [e.to_dict() for e in entities]
        
        return results
