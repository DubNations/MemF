from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from cognitive_os.conflict.conflict_manager import ConflictIssue
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.skills.base import BaseSkill


@dataclass(slots=True)
class SkillRegistration:
    skill: BaseSkill
    supported_issue_types: List[str] = field(default_factory=lambda: ["LOW_CONFIDENCE", "MISSING", "CONTRADICTION"])
    priority: int = 1
    timeout_ms: int = 300


@dataclass(slots=True)
class SkillExecutionReport:
    skill_name: str
    issue_type: str
    status: str
    produced_units: int
    detail: str = ""


@dataclass(slots=True)
class SkillManager:
    _registry: Dict[str, SkillRegistration] = field(default_factory=dict)

    def register(
        self,
        skill: BaseSkill,
        supported_issue_types: List[str] | None = None,
        priority: int = 1,
        timeout_ms: int = 300,
    ) -> None:
        self._registry[skill.name] = SkillRegistration(
            skill=skill,
            supported_issue_types=supported_issue_types or ["LOW_CONFIDENCE", "MISSING", "CONTRADICTION"],
            priority=priority,
            timeout_ms=timeout_ms,
        )

    def unregister(self, skill_name: str) -> None:
        self._registry.pop(skill_name, None)

    def execute(self, issue: ConflictIssue) -> Tuple[List[KnowledgeUnit], List[SkillExecutionReport]]:
        collected: List[KnowledgeUnit] = []
        reports: List[SkillExecutionReport] = []
        payload = {
            "type": issue.type,
            "message": issue.message,
            "knowledge_ids": issue.knowledge_ids,
            "topic": issue.topic,
            "reason_code": issue.reason_code,
        }

        ordered = sorted(self._registry.values(), key=lambda x: x.priority, reverse=True)
        for registration in ordered:
            if issue.type not in registration.supported_issue_types:
                continue
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(registration.skill.execute, payload)
                try:
                    result = future.result(timeout=registration.timeout_ms / 1000)
                    produced = len(result)
                    collected.extend(result)
                    reports.append(
                        SkillExecutionReport(
                            skill_name=registration.skill.name,
                            issue_type=issue.type,
                            status="success",
                            produced_units=produced,
                        )
                    )
                except TimeoutError:
                    reports.append(
                        SkillExecutionReport(
                            skill_name=registration.skill.name,
                            issue_type=issue.type,
                            status="timeout",
                            produced_units=0,
                            detail=f"timeout_ms={registration.timeout_ms}",
                        )
                    )
                except Exception as exc:
                    reports.append(
                        SkillExecutionReport(
                            skill_name=registration.skill.name,
                            issue_type=issue.type,
                            status="error",
                            produced_units=0,
                            detail=str(exc),
                        )
                    )
        return collected, reports
