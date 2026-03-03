from __future__ import annotations

import json
import random
from pathlib import Path

SCENARIOS = {
    "learning_exam_prep": {"size": 1200, "topic": "exam_prep"},
    "learning_skill_transition": {"size": 1100, "topic": "skill_transition"},
    "learning_language_retention": {"size": 1300, "topic": "language_retention"},
    "career_interview_prep": {"size": 1000, "topic": "interview"},
    "career_project_planning": {"size": 1150, "topic": "project_planning"},
    "career_networking": {"size": 1050, "topic": "networking"},
    "wellbeing_sleep_optimization": {"size": 1200, "topic": "sleep"},
    "wellbeing_nutrition_tracking": {"size": 1250, "topic": "nutrition"},
    "wellbeing_focus_management": {"size": 1400, "topic": "focus"},
}


def _mk_record(scenario: str, i: int, topic: str) -> dict:
    confidence = max(0.05, min(0.98, random.gauss(0.55, 0.2)))
    polarity = random.choice(["pro", "con", "pro", "pro"])
    source = random.choice(["private", "public", "human_verified"])
    return {
        "id": f"{scenario}_{i}",
        "knowledge_type": random.choice(["definition", "causal", "case", "frame"]),
        "content": {
            "topic": topic,
            "polarity": polarity,
            "summary": f"{scenario} observation #{i}",
            "reinforcement": round(random.uniform(0.0, 0.05), 4),
            "metadata": {
                "captured_from": random.choice(["mobile_note", "web_clip", "voice_memo", "manual_entry"]),
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
                f.write(json.dumps(_mk_record(name, i, config["topic"]), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    generate(Path("cognitive_os/experiments/data"))
