from __future__ import annotations

from pathlib import Path

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.rules.rule import Rule
from cognitive_os.skills.base import BaseSkill
from cognitive_os.skills.registry import SkillManager


class ConfidenceBoostSkill(BaseSkill):
    name = "confidence_boost"
    input_schema = {"type": "object"}
    output_schema = {"type": "array"}

    def execute(self, issue_context):
        if issue_context["type"] not in {"LOW_CONFIDENCE", "MISSING"}:
            return []
        return [
            KnowledgeUnit(
                id=f"skill_{kid}",
                knowledge_type="case",
                content=f"补充信息 for {kid}",
                source="public",
                confidence=0.75,
                valid_boundary="global",
            )
            for kid in issue_context["knowledge_ids"]
        ]


def bootstrap(memory: MemoryPlane) -> None:
    memory.save_rules(
        [
            Rule(
                id="r1",
                scope="demo",
                condition="knowledge_count >= 1",
                action_constraint="allow_next_step",
                priority=10,
                applicable_boundary="global",
            )
        ]
    )


def main() -> None:
    memory = MemoryPlane(Path("./data/memory.db"))
    bootstrap(memory)

    memory.save_knowledge_units(
        [
            KnowledgeUnit(
                id="k1",
                knowledge_type="definition",
                content="",
                source="public",
                confidence=0.1,
                valid_boundary="global",
            )
        ]
    )

    skill_manager = SkillManager()
    skill_manager.register(ConfidenceBoostSkill())

    loop = CognitiveLoop(memory, skill_manager)
    judgement = loop.run({"goal": "评估 demo 任务", "boundary": "global", "metadata": {"user": "demo"}})
    print(judgement)


if __name__ == "__main__":
    main()
