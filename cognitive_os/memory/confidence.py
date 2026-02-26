from __future__ import annotations

from datetime import datetime


def update_confidence(confidence_old: float, decay_factor: float, last_update: datetime, reinforcement: float) -> float:
    days = max((datetime.utcnow() - last_update).days, 0)
    confidence_new = confidence_old * (decay_factor**days) + reinforcement
    return max(0.0, min(1.0, confidence_new))
