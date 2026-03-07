from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from cognitive_os.rules.dsl_evaluator import evaluate_condition
from cognitive_os.rules.rule import Rule


def simulate_rules(
    rules: List[Rule],
    goal: str,
    boundary: str,
    metadata: Dict[str, Any] | None = None,
    knowledge_count: int = 0,
) -> Dict[str, Any]:
    env = {
        "goal": goal,
        "boundary": boundary,
        "knowledge_count": int(knowledge_count),
        "metadata": metadata or {},
    }

    matched: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for rule in sorted(rules, key=lambda r: r.priority, reverse=True):
        if rule.applicable_boundary not in {"global", boundary}:
            skipped.append({"rule_id": rule.id, "reason": "boundary_mismatch"})
            continue

        result = evaluate_condition(rule.condition, env)
        if not result.ok:
            diagnostics.append({"rule_id": rule.id, "error": result.error or "unknown"})
            continue
        if result.value:
            matched.append(
                {
                    "rule_id": rule.id,
                    "scope": rule.scope,
                    "priority": rule.priority,
                    "action_constraint": rule.action_constraint,
                    "condition": rule.condition,
                }
            )

    return {
        "env": env,
        "matched": matched,
        "diagnostics": diagnostics,
        "skipped": skipped,
        "rule_count": len(rules),
        "matched_count": len(matched),
    }
