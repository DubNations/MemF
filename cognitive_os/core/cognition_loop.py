from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List

from cognitive_os.conflict.conflict_manager import ConflictManager
from cognitive_os.core.context import CognitiveFrame, GoalContext
from cognitive_os.memory.confidence import update_confidence
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_engine import KnowledgeGraph, OntologyEngine
from cognitive_os.rules.rule_engine import Judgement, RuleEngine
from cognitive_os.skills.registry import SkillExecutionReport, SkillManager


@dataclass(slots=True)
class CognitiveFrameLoader:
    memory_plane: MemoryPlane

    def load(self, context: GoalContext) -> CognitiveFrame:
        _ = context
        return CognitiveFrame(
            rules=self.memory_plane.load_rules(),
            knowledge_units=self.memory_plane.load_knowledge_units(),
            ontology_entities=self.memory_plane.load_ontology_entities(),
        )


class ConfidenceUpdater:
    @staticmethod
    def update(knowledge_graph: KnowledgeGraph, memory_plane: MemoryPlane, decay_factor: float = 0.995) -> None:
        timestamps = {
            item["id"]: item["updated_at"] for item in memory_plane.load_knowledge_units_with_timestamps()
        }
        for unit in knowledge_graph.knowledge_units.values():
            last_update_raw = timestamps.get(unit.id)
            if last_update_raw:
                last_update = memory_plane.parse_datetime(last_update_raw)
            else:
                last_update = datetime.utcnow()
            reinforcement = 0.02
            if isinstance(unit.content, dict):
                reinforcement += float(unit.content.get("reinforcement", 0.0))
            unit.confidence = update_confidence(
                confidence_old=unit.confidence,
                decay_factor=decay_factor,
                last_update=last_update,
                reinforcement=reinforcement,
            )


class CognitiveLoop:
    def __init__(self, memory_plane: MemoryPlane, skill_manager: SkillManager) -> None:
        self.memory_plane = memory_plane
        self.skill_manager = skill_manager
        self.frame_loader = CognitiveFrameLoader(memory_plane)

    def run(self, goal_context: dict) -> Judgement:
        context = GoalContext(**goal_context)
        frame = self.frame_loader.load(context)
        knowledge_graph = OntologyEngine.assemble(frame)
        issues = ConflictManager.check(knowledge_graph)
        all_reports: List[SkillExecutionReport] = []

        for issue in issues:
            if issue.type in ["MISSING", "LOW_CONFIDENCE", "CONTRADICTION"]:
                new_info, reports = self.skill_manager.execute(issue)
                all_reports.extend(reports)
                knowledge_graph.update(new_info)

        judgement = RuleEngine.infer(knowledge_graph, context, frame.rules)
        ConfidenceUpdater.update(knowledge_graph, self.memory_plane)
        self.memory_plane.write_back(knowledge_graph, judgement)
        self.memory_plane.save_loop_run(
            goal=context.goal,
            boundary=context.boundary,
            skill_report=[asdict(report) for report in all_reports],
        )
        return judgement
