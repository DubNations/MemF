from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AgentTask:
    id: str
    name: str
    description: str = ""
    priority: int = 0
    assigned_to: Optional[str] = None
    status: str = "pending"
    result: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInfo:
    id: str
    name: str
    capabilities: List[str] = field(default_factory=list)
    status: str = "idle"
    current_task: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentCoordinator:
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._tasks: Dict[str, AgentTask] = {}
        self._task_queue: List[AgentTask] = []
        self._handlers: Dict[str, Callable] = {}
    
    def register_agent(self, agent: AgentInfo) -> None:
        self._agents[agent.id] = agent
    
    def unregister_agent(self, agent_id: str) -> None:
        if agent_id in self._agents:
            del self._agents[agent_id]
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        return self._agents.get(agent_id)
    
    def get_all_agents(self) -> List[AgentInfo]:
        return list(self._agents.values())
    
    def get_available_agents(self) -> List[AgentInfo]:
        return [
            agent for agent in self._agents.values()
            if agent.status == "idle"
        ]
    
    def register_handler(self, task_type: str, handler: Callable) -> None:
        self._handlers[task_type] = handler
    
    def submit_task(self, task: AgentTask) -> str:
        self._tasks[task.id] = task
        self._task_queue.append(task)
        self._task_queue.sort(key=lambda t: t.priority, reverse=True)
        return task.id
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        if task_id not in self._tasks:
            return False
        if agent_id not in self._agents:
            return False
        
        
        task = self._tasks[task_id]
        agent = self._agents[agent_id]
        
        if agent.status != "idle":
            return False
        
        task.assigned_to = agent_id
        task.status = "assigned"
        agent.status = "busy"
        agent.current_task = task_id
        
        return True
    
    def complete_task(self, task_id: str, result: Any) -> bool:
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        task.status = "completed"
        task.result = result
        
        if task.assigned_to:
            agent = self._agents.get(task.assigned_to)
            if agent:
                agent.status = "idle"
                agent.current_task = None
        
        return True
    
    def get_next_task(self) -> Optional[AgentTask]:
        if not self._task_queue:
            return None
        return self._task_queue.pop(0)
    
    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self._tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[AgentTask]:
        return [t for t in self._tasks.values() if t.status == "pending"]
    
    def get_agent_tasks(self, agent_id: str) -> List[AgentTask]:
        return [
            t for t in self._tasks.values()
            if t.assigned_to == agent_id
        ]
    
    def resolve_conflict(self, conflict: Dict[str, Any]) -> str:
        conflict_type = conflict.get("type", "resource")
        agents_involved = conflict.get("agents", [])
        
        if conflict_type == "resource":
            return self._resolve_resource_conflict(agents_involved, conflict)
        elif conflict_type == "task":
            return self._resolve_task_conflict(agents_involved, conflict)
        
        return "unresolved"
    
    def _resolve_resource_conflict(self, agents: List[str], conflict: Dict[str, Any]) -> str:
        return "negotiated"
    
    def _resolve_task_conflict(self, agents: List[str], conflict: Dict[str, Any]) -> str:
        return "reassigned"
    
    def broadcast_message(self, message: Dict[str, Any]) -> None:
        for agent in self._agents.values():
            if agent.status == "idle":
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_agents": len(self._agents),
            "idle_agents": len([a for a in self._agents.values() if a.status == "idle"]),
            "busy_agents": len([a for a in self._agents.values() if a.status == "busy"]),
            "total_tasks": len(self._tasks),
            "pending_tasks": len(self.get_pending_tasks()),
            "completed_tasks": len([t for t in self._tasks.values() if t.status == "completed"]),
        }
