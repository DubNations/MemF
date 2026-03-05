import time

from cognitive_os.conflict.conflict_manager import ConflictIssue
from cognitive_os.skills.base import BaseSkill
from cognitive_os.skills.registry import SkillManager


class SlowSkill(BaseSkill):
    name = "slow"

    def execute(self, issue_context):
        time.sleep(0.2)
        return []


class FastSkill(BaseSkill):
    name = "fast"

    def execute(self, issue_context):
        return []


def test_skill_timeout_and_routing():
    manager = SkillManager()
    manager.register(SlowSkill(), supported_issue_types=["LOW_CONFIDENCE"], timeout_ms=50)
    manager.register(FastSkill(), supported_issue_types=["MISSING"], timeout_ms=200)

    units, report = manager.execute(ConflictIssue(type="LOW_CONFIDENCE", message="m", knowledge_ids=["k1"]))
    assert units == []
    assert len(report) == 1
    assert report[0].status == "timeout"

    units2, report2 = manager.execute(ConflictIssue(type="MISSING", message="m", knowledge_ids=["k1"]))
    assert len(report2) == 1
    assert report2[0].skill_name == "fast"
    assert report2[0].status == "success"
