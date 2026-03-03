from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.rules.rule import Rule
from cognitive_os.skills.base import BaseSkill
from cognitive_os.skills.registry import SkillManager

DATA_DIR = Path("cognitive_os/experiments/data")
REPORT_DIR = Path("cognitive_os/experiments/reports")
DB_PATH = Path("data/personal_knowledge_experiment.db")


class EnrichmentSkill(BaseSkill):
    name = "enrichment_skill"

    def execute(self, issue_context):
        if issue_context["type"] not in {"LOW_CONFIDENCE", "MISSING", "CONTRADICTION"}:
            return []
        results = []
        for kid in issue_context["knowledge_ids"][:5]:
            results.append(
                KnowledgeUnit(
                    id=f"enriched_{issue_context['type'].lower()}_{kid}",
                    knowledge_type="causal",
                    content={
                        "topic": issue_context.get("topic", "generic"),
                        "polarity": "pro",
                        "summary": f"Auto-enriched context for {kid}",
                        "reinforcement": 0.03,
                    },
                    source="public",
                    confidence=0.82,
                    valid_boundary="global",
                )
            )
        return results


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _setup_rules(memory: MemoryPlane) -> None:
    memory.save_rules(
        [
            Rule(
                id="pk_rule_high_volume",
                scope="personal_knowledge",
                condition="knowledge_count >= 1000",
                action_constraint="prioritize_structured_review",
                priority=10,
                applicable_boundary="global",
            ),
            Rule(
                id="pk_rule_medium_volume",
                scope="personal_knowledge",
                condition="knowledge_count >= 300",
                action_constraint="weekly_digest_generation",
                priority=8,
                applicable_boundary="global",
            ),
            Rule(
                id="pk_rule_goal_context",
                scope="personal_knowledge",
                condition="metadata['scenario'] in ['learning_exam_prep','career_interview_prep','wellbeing_focus_management']",
                action_constraint="deep_focus_mode",
                priority=6,
                applicable_boundary="global",
            ),
        ]
    )


def _scenario_files() -> list[Path]:
    return sorted(DATA_DIR.glob("*.jsonl"))


def run() -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    memory = MemoryPlane(DB_PATH)
    _setup_rules(memory)

    skill_manager = SkillManager()
    skill_manager.register(EnrichmentSkill(), supported_issue_types=["LOW_CONFIDENCE", "MISSING", "CONTRADICTION"], timeout_ms=500)
    loop = CognitiveLoop(memory, skill_manager)

    rounds = {
        "round_1_validation": {"focus": "有效性验证", "useful": [], "improvable": [], "unusable": []},
        "round_2_optimization": {"focus": "可提升项优化", "useful": [], "improvable": [], "unusable": []},
        "round_3_generalization": {"focus": "不可用点泛化重构", "useful": [], "improvable": [], "unusable": []},
    }

    scenario_results = []
    for path in _scenario_files():
        scenario = path.stem
        dataset = _load_jsonl(path)
        ingest_result = memory.save_knowledge_units_bulk(dataset)

        start = time.time()
        judgement = loop.run({"goal": f"Assess scenario {scenario}", "boundary": "global", "metadata": {"scenario": scenario}})
        latency_ms = int((time.time() - start) * 1000)

        decisions = [d["action_constraint"] for d in judgement.decisions]
        diag_cnt = len(judgement.diagnostics)
        scenario_results.append(
            {
                "scenario": scenario,
                "sample_size": len(dataset),
                "ingested": len(ingest_result["inserted"]),
                "deduplicated": len(ingest_result["skipped"]),
                "latency_ms": latency_ms,
                "decision_count": len(decisions),
                "decisions": decisions,
                "diagnostics_count": diag_cnt,
            }
        )

    # classification logic for 3 rounds
    for item in scenario_results:
        if item["decision_count"] > 0 and item["latency_ms"] < 1500:
            rounds["round_1_validation"]["useful"].append(item["scenario"])
        else:
            rounds["round_1_validation"]["improvable"].append(item["scenario"])

        if item["diagnostics_count"] > 0:
            rounds["round_2_optimization"]["improvable"].append(item["scenario"])
        else:
            rounds["round_2_optimization"]["useful"].append(item["scenario"])

        if item["latency_ms"] >= 2500:
            rounds["round_3_generalization"]["unusable"].append(item["scenario"])
        elif item["latency_ms"] >= 1500:
            rounds["round_3_generalization"]["improvable"].append(item["scenario"])
        else:
            rounds["round_3_generalization"]["useful"].append(item["scenario"])

    summary = {
        "total_scenarios": len(scenario_results),
        "scenario_results": scenario_results,
        "rounds": rounds,
    }
    (REPORT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def write_markdown(summary: dict) -> None:
    lines = [
        "# Personal Knowledge Service: 3-Round Validation & Iteration",
        "",
        f"- Total scenarios: {summary['total_scenarios']}",
        "- Domain focus: Personal Knowledge Service only",
        "",
        "## Scenario-level metrics",
        "",
        "| Scenario | Sample Size | Ingested | Deduplicated | Latency (ms) | Decisions | Diagnostics |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["scenario_results"]:
        lines.append(
            f"| {item['scenario']} | {item['sample_size']} | {item['ingested']} | {item['deduplicated']} | {item['latency_ms']} | {item['decision_count']} | {item['diagnostics_count']} |"
        )

    lines += ["", "## Iteration records"]
    for round_name, info in summary["rounds"].items():
        lines += [f"### {round_name} ({info['focus']})", f"- Useful: {', '.join(info['useful']) or 'None'}"]
        lines += [f"- Improvable: {', '.join(info['improvable']) or 'None'}"]
        lines += [f"- Unusable: {', '.join(info['unusable']) or 'None'}", ""]

    lines += [
        "## Processing actions implemented",
        "- Useful -> standardized ops: batch ingestion, deterministic dataset generation, single-command evaluation runner.",
        "- Improvable -> optimization: safe DSL evaluator, rule diagnostics, skill routing/timeout isolation, contradiction detection.",
        "- Unusable -> generalized reconstruction: loop run telemetry persistence and reproducible report artifact.",
    ]
    (REPORT_DIR / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    summary_data = run()
    write_markdown(summary_data)
    print(json.dumps(summary_data, ensure_ascii=False, indent=2))
