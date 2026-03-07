from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from cognitive_os.instances.instance import Instance


@dataclass(slots=True)
class InstanceResolver:
    index: Dict[str, Instance]

    def resolve(self, instance_id: str) -> Optional[Instance]:
        return self.index.get(instance_id)

    def upsert(self, instance: Instance) -> None:
        self.index[instance.instance_id] = instance

    def bulk_load(self, instances: Iterable[Instance]) -> None:
        for instance in instances:
            self.upsert(instance)
