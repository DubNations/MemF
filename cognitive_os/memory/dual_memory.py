from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class IndividualMemory:
    agent_id: str
    states: List[Dict[str, Any]] = field(default_factory=list)
    max_states: int = 100
    
    def __init__(self, agent_id: str, max_states: int = 100):
        self.agent_id = agent_id
        self._max_states = max_states
        self._states: List[Dict[str, Any]] = []
    
    def add_state(self, state: Dict[str, Any]) -> None:
        self._states.append(state)
        if len(self._states) > self._max_states:
            self._states = self._states[-self._max_states:]
    
    def get_states(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit:
            return self._states[-limit:]
        return self._states.copy()
    
    def get_latest_state(self) -> Optional[Dict[str, Any]]:
        if self._states:
            return self._states[-1]
        return None
    
    def clear(self) -> None:
        self._states = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "states": self._states,
            "max_states": self._max_states,
        }


@dataclass
class CollectiveMemory:
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    max_interactions: int = 1000
    
    def __init__(self, max_interactions: int = 1000):
        self._interactions: List[Dict[str, Any]] = []
        self._max_interactions = max_interactions
    
    def add_interaction(self, interaction: Dict[str, Any]) -> None:
        self._interactions.append(interaction)
        if len(self._interactions) > self._max_interactions:
            self._interactions = self._interactions[-self._max_interactions:]
    
    def get_interactions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit:
            return self._interactions[-limit:]
        return self._interactions.copy()
    
    def get_latest_interactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._interactions[-limit:]
    
    def clear(self) -> None:
        self._interactions = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interactions": self._interactions,
            "max_interactions": self._max_interactions,
        }


class DualMemorySystem:
    def __init__(self, db_path: str = "./data/dual_memory.db"):
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._individual_memories: Dict[str, IndividualMemory] = {}
        self._collective_memory = CollectiveMemory()
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
            CREATE TABLE IF NOT EXISTS individual_memory (
                agent_id TEXT PRIMARY KEY,
                states TEXT,
                max_states INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collective_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interactions TEXT,
                max_interactions INTEGER DEFAULT 1000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()
    
    def get_individual_memory(self, agent_id: str) -> IndividualMemory:
        if agent_id not in self._individual_memories:
            self._individual_memories[agent_id] = IndividualMemory(agent_id)
            return self._individual_memories[agent_id]
        
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM individual_memory WHERE agent_id = ?",
            (agent_id,),
        )
        row = cursor.fetchone()
        if self._db_path != ":memory:":
            conn.close()
        
        if row:
            memory = IndividualMemory(
                agent_id=row["agent_id"],
                states=json.loads(row["states"]) if row["states"] else [],
                max_states=row["max_states"],
            )
            self._individual_memories[agent_id] = memory
            return memory
        memory = IndividualMemory(agent_id)
        self._individual_memories[agent_id] = memory
        return memory
    
    def save_individual_state(
        self,
        agent_id: str,
        state: Dict[str, Any],
    ) -> None:
        memory = self.get_individual_memory(agent_id)
        memory.add_state(state)
        
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO individual_memory (agent_id, states, max_states)
            VALUES (?, ?, ?)
            """,
            (agent_id, json.dumps(memory.states), memory.max_states),
        )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()
    
    def get_collective_memory(self) -> CollectiveMemory:
        return self._collective_memory
    
    def save_collective_interaction(self, interaction: Dict[str, Any]) -> None:
        self._collective_memory.add_interaction(interaction)
        
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO collective_memory (interactions, max_interactions)
            VALUES (?, ?)
            """,
            (json.dumps(self._collective_memory.interactions), self._collective_memory.max_interactions),
        )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()
    
    def get_shared_knowledge(self, agent_ids: List[str]) -> List[Dict[str, Any]]:
        shared = []
        for agent_id in agent_ids:
            memory = self.get_individual_memory(agent_id)
            shared.extend(memory.states)
        return shared
    
    def get_interaction_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._collective_memory.get_latest_interactions(limit)
    
    def clear_agent_memory(self, agent_id: str) -> None:
        if agent_id in self._individual_memories:
            del self._individual_memories[agent_id]
        
        conn = self._get_connection()
        conn.execute("DELETE FROM individual_memory WHERE agent_id = ?", (agent_id,))
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "individual_memories": len(self._individual_memories),
            "collective_interactions": len(self._collective_memory.interactions),
        }
