from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class RerankerConfig:
    supplier: str = "cohere"
    model: str = "rerank-multilingual-v3.0"
    top_n: int = 5
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RerankerConfig":
        return cls(
            supplier=data.get("supplier", "cohere"),
            model=data.get("model", "rerank-multilingual-v3.0"),
            top_n=data.get("top_n", 5),
            enabled=data.get("enabled", True),
        )


@dataclass
class LLMConfig:
    max_input_tokens: int = 4000
    temperature: float = 0.7
    model: str = "deepseek-chat"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfig":
        return cls(
            max_input_tokens=data.get("max_input_tokens", 4000),
            temperature=data.get("temperature", 0.7),
            model=data.get("model", "deepseek-chat"),
        )


@dataclass
class NodeConfig:
    name: str
    edges: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "NodeConfig":
        return cls(
            name=name,
            edges=data.get("edges", []),
        )


@dataclass
class WorkflowConfig:
    name: str = "standard_rag"
    nodes: List[NodeConfig] = field(default_factory=list)
    max_history: int = 10
    reranker_config: Optional[RerankerConfig] = None
    llm_config: Optional[LLMConfig] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowConfig":
        workflow_data = data.get("workflow_config", {})
        nodes = []
        for node_data in workflow_data.get("nodes", []):
            nodes.append(NodeConfig.from_dict(node_data.get("name", ""), node_data))

        reranker_data = data.get("reranker_config")
        reranker_config = RerankerConfig.from_dict(reranker_data) if reranker_data else None

        llm_data = data.get("llm_config")
        llm_config = LLMConfig.from_dict(llm_data) if llm_data else None

        return cls(
            name=workflow_data.get("name", "standard_rag"),
            nodes=nodes,
            max_history=data.get("max_history", 10),
            reranker_config=reranker_config,
            llm_config=llm_config,
        )

    @classmethod
    def from_yaml(cls, path: str) -> "WorkflowConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data or {})

    def get_node_order(self) -> List[str]:
        if not self.nodes:
            return ["START", "retrieve", "generate", "END"]
        return [node.name for node in self.nodes]

    def has_node(self, node_name: str) -> bool:
        return any(node.name == node_name for node in self.nodes)


@dataclass
class RetrievalConfig:
    workflow_config: Optional[WorkflowConfig] = None
    top_k: int = 8
    use_query_rewrite: bool = True
    use_reranker: bool = True
    use_history: bool = True

    @classmethod
    def from_yaml(cls, path: str) -> "RetrievalConfig":
        workflow_config = WorkflowConfig.from_yaml(path)
        return cls(workflow_config=workflow_config)

    @classmethod
    def default(cls) -> "RetrievalConfig":
        default_workflow = WorkflowConfig(
            name="cognitive_rag",
            nodes=[
                NodeConfig(name="START", edges=["rewrite"]),
                NodeConfig(name="rewrite", edges=["retrieve"]),
                NodeConfig(name="retrieve", edges=["rerank"]),
                NodeConfig(name="rerank", edges=["generate"]),
                NodeConfig(name="generate", edges=["END"]),
            ],
            max_history=10,
            reranker_config=RerankerConfig(),
            llm_config=LLMConfig(),
        )
        return cls(workflow_config=default_workflow)

    @property
    def reranker_enabled(self) -> bool:
        if self.workflow_config and self.workflow_config.reranker_config:
            return self.workflow_config.reranker_config.enabled and self.use_reranker
        return False


DEFAULT_WORKFLOW_YAML = """
workflow_config:
  name: "cognitive_rag"
  nodes:
    - name: "START"
      edges: ["rewrite"]
    
    - name: "rewrite"
      edges: ["retrieve"]
    
    - name: "retrieve"
      edges: ["conflict_check"]
    
    - name: "conflict_check"
      edges: ["skill_execution", "rule_inference"]
    
    - name: "skill_execution"
      edges: ["generate"]
    
    - name: "rule_inference"
      edges: ["generate"]
    
    - name: "generate"
      edges: ["END"]

max_history: 10

reranker_config:
  supplier: "cohere"
  model: "rerank-multilingual-v3.0"
  top_n: 5
  enabled: true

llm_config:
  max_input_tokens: 4000
  temperature: 0.7
"""


def create_default_workflow_yaml(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(DEFAULT_WORKFLOW_YAML.strip())
