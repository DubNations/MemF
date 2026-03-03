from __future__ import annotations

import json
import random
from pathlib import Path

SCENARIOS = {
    "health_chronic_care_manager": {"size": 1600, "topic": "chronic_care", "persona": "慢病患者管理师"},
    "health_nutrition_planner": {"size": 1500, "topic": "nutrition_plan", "persona": "家庭营养管理师"},
    "efficiency_focus_coach": {"size": 1450, "topic": "focus_coaching", "persona": "专注力教练"},
    "finance_wealth_advisor": {"size": 1700, "topic": "wealth_advice", "persona": "个人理财顾问"},
    "finance_insurance_consultant": {"size": 1550, "topic": "insurance_clause", "persona": "保险咨询师"},
    "education_exam_coach": {"size": 1650, "topic": "exam_coaching", "persona": "考试备考教练"},
    "career_transition_advisor": {"size": 1500, "topic": "career_transition", "persona": "职业转型顾问"},
    "career_project_retrospective": {"size": 1400, "topic": "project_retrospective", "persona": "项目复盘教练"},
    "marketing_customer_service_assistant": {"size": 1800, "topic": "policy_lookup", "persona": "营销客服助手"},
}


def _mk_record(scenario: str, i: int, topic: str, persona: str) -> dict:
    confidence = max(0.05, min(0.98, random.gauss(0.57, 0.18)))
    polarity = random.choice(["pro", "con", "pro", "pro"])
    source = random.choice(["private", "public", "human_verified"])
    return {
        "id": f"{scenario}_{i}",
        "knowledge_type": random.choice(["definition", "causal", "case", "frame"]),
        "content": {
            "topic": topic,
            "polarity": polarity,
            "summary": f"{persona} observation #{i} for {scenario}",
            "reinforcement": round(random.uniform(0.0, 0.05), 4),
            "metadata": {
                "persona": persona,
                "captured_from": random.choice(["pdf_policy", "doc_sop", "web_clip", "manual_entry"]),
                "day_offset": random.randint(0, 365),
            },
        },
        "source": source,
        "confidence": round(confidence, 4),
        "valid_boundary": "global",
        "invalid_boundary": "",
        "conflict_ids": [],
    }


def generate(output_dir: Path) -> None:
    random.seed(42)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, config in SCENARIOS.items():
        path = output_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for i in range(config["size"]):
                f.write(
                    json.dumps(
                        _mk_record(name, i, config["topic"], config["persona"]),
                        ensure_ascii=False,
                    )
                    + "\n"
                )


if __name__ == "__main__":
    generate(Path("cognitive_os/experiments/data"))
