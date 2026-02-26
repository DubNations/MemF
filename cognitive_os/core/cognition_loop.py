from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from cognitive_os.conflict.conflict_manager import ConflictManager
from cognitive_os.core.context import CognitiveFrame, GoalContext
from cognitive_os.memory.confidence import update_confidence
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_engine import KnowledgeGraph, OntologyEngine
from cognitive_os.rules.rule_engine import Judgement, RuleEngine
from cognitive_os.skills.registry import SkillManager


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
    def update(knowledge_graph: KnowledgeGraph, decay_factor: float = 0.995) -> None:
        pseudo_last_update = datetime.utcnow() - timedelta(days=1)
        for unit in knowledge_graph.knowledge_units.values():
            unit.confidence = update_confidence(
                confidence_old=unit.confidence,
                decay_factor=decay_factor,
                last_update=pseudo_last_update,
                reinforcement=0.02,
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

        for issue in issues:
            if issue.type in ["MISSING", "LOW_CONFIDENCE"]:
                new_info = self.skill_manager.execute(issue)
                knowledge_graph.update(new_info)

        judgement = RuleEngine.infer(knowledge_graph, context, frame.rules)
        self.memory_plane.write_back(knowledge_graph, judgement)
        ConfidenceUpdater.update(knowledge_graph)
        self.memory_plane.write_back(knowledge_graph, judgement)

        return judgement
