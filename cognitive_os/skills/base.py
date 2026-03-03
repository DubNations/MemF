from __future__ import annotations

from typing import Any, Dict, List

from cognitive_os.ontology.ontology_entity import KnowledgeUnit


class BaseSkill:
    name = "string"
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    permission = "read_only"

    def execute(self, issue_context: Dict[str, Any]) -> List[KnowledgeUnit]:
        raise NotImplementedError
