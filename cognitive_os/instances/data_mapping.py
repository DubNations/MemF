from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class DataMapping:
    mapping_id: str
    data_source_type: str
    connection_config: Dict[str, Any] = field(default_factory=dict)
    field_mapping: Dict[str, Any] = field(default_factory=dict)
    refresh_policy: str = "on_demand"
    validation_rule: str = ""
