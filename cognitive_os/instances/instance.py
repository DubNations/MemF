from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class Instance:
    instance_id: str
    ontology_type: str
    state: str
    related_instances: List[str] = field(default_factory=list)
    data_mapping_refs: List[str] = field(default_factory=list)
