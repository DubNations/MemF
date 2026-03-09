from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from cognitive_os.knowledge.graph_rag.entity_extractor import Entity, Relation


@dataclass
class KnowledgeGraph:
    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: Dict[str, Relation] = field(default_factory=dict)
    
    def add_entity(self, entity: Entity) -> None:
        self.entities[entity.id] = entity
    
    def add_relation(self, relation: Relation) -> None:
        self.relations[relation.id] = relation
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)
    
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        for e in self.entities.values():
            if e.name.lower() == name.lower():
                return e
        return None
    
    def get_related_entities(self, entity_id: str, relation_type: Optional[str] = None) -> List[Entity]:
        related = []
        for r in self.relations.values():
            if r.source_id == entity_id:
                if relation_type is None or r.relation_type == relation_type:
                    target = self.entities.get(r.target_id)
                    if target:
                        related.append(target)
            elif r.target_id == entity_id:
                if relation_type is None or r.relation_type == relation_type:
                source = self.entities.get(r.source_id)
                if source:
                    related.append(source)
        return related
    
    def get_relations_for_entity(self, entity_id: str) -> List[Relation]:
        return [
            r for r in self.relations.values()
            if r.source_id == entity_id or r.target_id == entity_id
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "relations": {k: v.to_dict() for k, v in self.relations.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraph":
        graph = cls()
        for k, v in data.get("entities", {}).items():
            graph.entities[k] = Entity(
                id=v["id"],
                name=v["name"],
                entity_type=v["entity_type"],
                description=v.get("description", ""),
                properties=v.get("properties", {}),
                confidence=v.get("confidence", 0.8),
            )
        for k, v in data.get("relations", {}).items():
            graph.relations[k] = Relation(
                id=v["id"],
                source_id=v["source_id"],
                target_id=v["target_id"],
                relation_type=v["relation_type"],
                description=v.get("description", ""),
                properties=v.get("properties", {}),
                confidence=v.get("confidence", 0.8),
            )
        return graph


class GraphBuilder:
    def __init__(self, db_path: str = "./data/knowledge_graph.db"):
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._graph = KnowledgeGraph()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:")
            return self._conn
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                description TEXT,
                properties TEXT,
                confidence REAL DEFAULT 0.8,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                description TEXT,
                properties TEXT,
                confidence REAL DEFAULT 0.8,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES kg_entities(id),
                FOREIGN KEY (target_id) REFERENCES kg_entities(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_name ON kg_entities(name)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_relation_source ON kg_relations(source_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_relation_target ON kg_relations(target_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_relation_type ON kg_relations(relation_type)
        """)
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def build_from_text(
        self,
        text: str,
        doc_id: Optional[str] = None,
        extractor=None,
    ) -> KnowledgeGraph:
        from cognitive_os.knowledge.graph_rag.entity_extractor import EntityExtractor
        
        if extractor is None:
            extractor = EntityExtractor()
        
        entities, relations = extractor.extract_entities(text)
        
        if doc_id:
            for e in entities:
                e.properties["source_doc"] = doc_id
            for r in relations:
                r.properties["source_doc"] = doc_id
        
        for entity in entities:
            self.add_entity(entity)
        
        for relation in relations:
            self.add_relation(relation)
        
        return self._graph

    def add_entity(self, entity: Entity) -> None:
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO kg_entities 
            (id, name, entity_type, description, properties, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entity.id,
                entity.name,
                entity.entity_type,
                entity.description,
                json.dumps(entity.properties),
                entity.confidence,
            ),
        )
        conn.commit()
        self._graph.add_entity(entity)
        if self._db_path != ":memory:":
            conn.close()

    def add_relation(self, relation: Relation) -> None:
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO kg_relations 
            (id, source_id, target_id, relation_type, description, properties, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation.id,
                relation.source_id,
                relation.target_id,
                relation.relation_type,
                relation.description,
                json.dumps(relation.properties),
                relation.confidence,
            ),
        )
        conn.commit()
        self._graph.add_relation(relation)
        if self._db_path != ":memory:":
            conn.close()

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM kg_entities WHERE id = ?",
            (entity_id,),
        )
        row = cursor.fetchone()
        if self._db_path != ":memory:":
            conn.close()
        
        if not row:
                return None
        
        return Entity(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            description=row["description"] or "",
            properties=json.loads(row["properties"] or "{}"),
            confidence=row["confidence"],
        )

    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM kg_entities WHERE LOWER(name) = LOWER(?)",
            (name,),
        )
        row = cursor.fetchone()
        if self._db_path != ":memory:":
            conn.close()
        
        if not row:
            return None
        
        return Entity(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            description=row["description"] or "",
            properties=json.loads(row["properties"] or "{}"),
            confidence=row["confidence"],
        )

    def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Entity]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        
        sql = "SELECT * FROM kg_entities WHERE name LIKE ?"
        params = [f"%{query}%"]
        
        if entity_type:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        
        sql += f" ORDER BY confidence DESC LIMIT {limit}"
        
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        if self._db_path != ":memory:":
            conn.close()
        
        return [
            Entity(
                id=row["id"],
                name=row["name"],
                entity_type=row["entity_type"],
                description=row["description"] or "",
                properties=json.loads(row["properties"] or "{}"),
                confidence=row["confidence"],
            )
            for row in rows
        ]

    def get_relations_for_entity(self, entity_id: str) -> List[Relation]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT * FROM kg_relations 
            WHERE source_id = ? OR target_id = ?
            """,
            (entity_id, entity_id),
        )
        rows = cursor.fetchall()
        if self._db_path != ":memory:":
            conn.close()
        
        return [
            Relation(
                id=row["id"],
                source_id=row["source_id"],
                target_id=row["target_id"],
                relation_type=row["relation_type"],
                description=row["description"] or "",
                properties=json.loads(row["properties"] or "{}"),
                confidence=row["confidence"],
            )
            for row in rows
        ]

    def get_related_entities(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        max_depth: int = 2,
    ) -> List[Entity]:
        visited: Set[str] = set()
        result: List[Entity] = []
        
        def _traverse(eid: str, depth: int) -> None:
            if depth > max_depth or eid in visited:
                return
            visited.add(eid)
            
            relations = self.get_relations_for_entity(eid)
            for r in relations:
                if relation_type and r.relation_type != relation_type:
                    continue
                
                target_id = r.target_id if r.source_id == eid else r.source_id
                if target_id not in visited:
                    entity = self.get_entity(target_id)
                    if entity:
                        result.append(entity)
                        _traverse(target_id, depth + 1)
        
        _traverse(entity_id, 0)
        return result

    def get_graph_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        
        cursor = conn.execute("SELECT COUNT(*) FROM kg_entities")
        entity_count = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM kg_relations")
        relation_count = cursor.fetchone()[0]
        
        cursor = conn.execute(
            "SELECT entity_type, COUNT(*) FROM kg_entities GROUP BY entity_type"
        )
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor = conn.execute(
            "SELECT relation_type, COUNT(*) FROM kg_relations GROUP BY relation_type"
        )
        by_relation = {row[0]: row[1] for row in cursor.fetchall()}
        
        if self._db_path != ":memory:":
            conn.close()
        
        return {
            "total_entities": entity_count,
            "total_relations": relation_count,
            "entities_by_type": by_type,
            "relations_by_type": by_relation,
        }

    def clear_all(self) -> None:
        conn = self._get_connection()
        conn.execute("DELETE FROM kg_relations")
        conn.execute("DELETE FROM kg_entities")
        conn.commit()
        self._graph = KnowledgeGraph()
        if self._db_path != ":memory:":
            conn.close()
