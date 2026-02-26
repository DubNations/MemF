from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from cognitive_os.conflict.conflict_manager import ConflictIssue
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.skills.base import BaseSkill


@dataclass(slots=True)
class SkillManager:
    _registry: Dict[str, BaseSkill] = field(default_factory=dict)

    def register(self, skill: BaseSkill) -> None:
        self._registry[skill.name] = skill

    def unregister(self, skill_name: str) -> None:
        self._registry.pop(skill_name, None)

    def execute(self, issue: ConflictIssue) -> List[KnowledgeUnit]:
        collected: List[KnowledgeUnit] = []
        payload = {
            "type": issue.type,
            "message": issue.message,
            "knowledge_ids": issue.knowledge_ids,
        }
        for skill in self._registry.values():
            collected.extend(skill.execute(payload))
        return collected
