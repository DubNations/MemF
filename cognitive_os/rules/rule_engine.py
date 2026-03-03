from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from cognitive_os.core.context import GoalContext
from cognitive_os.ontology.ontology_engine import KnowledgeGraph
from cognitive_os.rules.dsl_evaluator import evaluate_condition
from cognitive_os.rules.rule import Rule


@dataclass(slots=True)
class Judgement:
    goal: str
    decisions: List[Dict[str, str]]
    diagnostics: List[Dict[str, str]] = field(default_factory=list)


class RuleEngine:
    @staticmethod
    def infer(knowledge_graph: KnowledgeGraph, context: GoalContext, rules: List[Rule]) -> Judgement:
        ordered = sorted(rules, key=lambda r: r.priority, reverse=True)
        decisions: List[Dict[str, str]] = []
        diagnostics: List[Dict[str, str]] = []
        env = {
            "goal": context.goal,
            "boundary": context.boundary,
            "knowledge_count": len(knowledge_graph.knowledge_units),
            "metadata": context.metadata,
        }
        for rule in ordered:
            if rule.applicable_boundary not in {"global", context.boundary}:
                continue
            result = evaluate_condition(rule.condition, env)
            if not result.ok:
                diagnostics.append({"rule_id": rule.id, "error": result.error or "unknown"})
                continue
            if result.value:
                decisions.append(
                    {
                        "rule_id": rule.id,
                        "scope": rule.scope,
                        "action_constraint": rule.action_constraint,
                    }
                )
        return Judgement(goal=context.goal, decisions=decisions, diagnostics=diagnostics)
