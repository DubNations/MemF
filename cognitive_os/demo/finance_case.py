from __future__ import annotations

from pathlib import Path

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.rules.rule import Rule
from cognitive_os.skills.base import BaseSkill
from cognitive_os.skills.registry import SkillManager


class LoanDataSkill(BaseSkill):
    name = "loan_data_enricher"
    input_schema = {"type": "object"}
    output_schema = {"type": "array"}

    def execute(self, issue_context):
        if issue_context["type"] not in {"LOW_CONFIDENCE", "MISSING"}:
            return []
        items = []
        for kid in issue_context["knowledge_ids"]:
            items.append(
                KnowledgeUnit(
                    id=f"enriched_{kid}",
                    knowledge_type="causal",
                    content={"income_stability": "medium", "debt_ratio": 0.58},
                    source="public",
                    confidence=0.8,
                    valid_boundary="global",
                )
            )
        return items


def bootstrap(memory: MemoryPlane) -> None:
    memory.save_rules(
        [
            Rule(
                id="loan_risk_high",
                scope="finance",
                condition="knowledge_count >= 2",
                action_constraint="require_manual_review",
                priority=10,
                applicable_boundary="global",
            ),
            Rule(
                id="loan_risk_basic",
                scope="finance",
                condition="knowledge_count >= 1",
                action_constraint="collect_more_documents",
                priority=5,
                applicable_boundary="global",
            ),
        ]
    )

    memory.save_knowledge_units(
        [
            KnowledgeUnit(
                id="applicant_profile",
                knowledge_type="definition",
                content="申请人信用评分 600，历史逾期 1 次",
                source="public",
                confidence=0.3,
                valid_boundary="global",
            )
        ]
    )


def main() -> None:
    memory = MemoryPlane(Path("./data/finance_case.db"))
    bootstrap(memory)

    skill_manager = SkillManager()
    skill_manager.register(LoanDataSkill())

    loop = CognitiveLoop(memory, skill_manager)
    judgement = loop.run(
        {
            "goal": "贷款预审：确定是否进入人工复核",
            "boundary": "global",
            "metadata": {"domain": "finance", "product": "loan"},
        }
    )

    print("=== Finance Scenario Result ===")
    print(judgement)
    print("=== Recent Judgements ===")
    print(memory.load_judgements(limit=3))


if __name__ == "__main__":
    main()
