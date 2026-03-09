from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from cognitive_os.ontology.ontology_entity import KnowledgeUnit


@dataclass
class DecayConfig:
    decay_rate: float = 0.05
    min_confidence: float = 0.1
    use_count_resistance: float = 0.01
    decay_smoothing: float = 1.0


class KnowledgeHalfLifeManager:
    def __init__(self, config: Optional[DecayConfig] = None) -> None:
        self.config = config or DecayConfig()

    def calculate_decayed_confidence(self, ku: KnowledgeUnit) -> float:
        current_time = time.time()
        
        if ku.last_used_at <= 0:
            ku.last_used_at = current_time
        
        days_since_last_use = (current_time - ku.last_used_at) / (24 * 3600)
        
        if days_since_last_use <= 0:
            return ku.confidence
        
        use_count = max(1, ku.use_count)
        resistance = math.log10(1 + use_count) * self.config.use_count_resistance
        effective_decay = max(0.001, self.config.decay_rate - resistance)
        
        decay_factor = math.exp(-effective_decay * days_since_last_use * self.config.decay_smoothing)
        new_confidence = ku.confidence * decay_factor
        
        return max(self.config.min_confidence, min(1.0, new_confidence))

    def record_usage(self, ku: KnowledgeUnit) -> None:
        ku.last_used_at = time.time()
        ku.use_count += 1

    def should_prune(self, ku: KnowledgeUnit) -> bool:
        decayed_conf = self.calculate_decayed_confidence(ku)
        return decayed_conf <= self.config.min_confidence + 0.01

    def refresh_knowledge(self, ku: KnowledgeUnit, boost: float = 0.1) -> None:
        ku.last_used_at = time.time()
        ku.use_count += 1
        ku.confidence = min(1.0, ku.confidence + boost)
