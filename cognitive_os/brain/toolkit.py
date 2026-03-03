from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.ingestion.document_pipeline import DocumentPipeline
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.vector.vector_store import LocalVectorDB


class BrainToolkit:
    def __init__(self, memory: MemoryPlane, loop: CognitiveLoop, vector_db: LocalVectorDB) -> None:
        self.memory = memory
        self.loop = loop
        self.vector_db = vector_db

    def upload_document(self, filename: str, content_base64: str, scenario: str, source: str = "private") -> Dict[str, Any]:
        parse_result, text = DocumentPipeline.parse_base64_document(filename, content_base64)
        metadata = DocumentPipeline.map_document_metadata(parse_result, scenario)
        self.memory.save_document_record(metadata)
        if parse_result.status != "OK":
            return {"status": "FAILED", "metadata": metadata, "ingested": 0}

        units = DocumentPipeline.to_knowledge_units(filename, text, scenario=scenario, source=source)
        result = self.memory.save_knowledge_units_bulk([asdict(u) for u in units])
        for u in units:
            summary = u.content.get("summary", "") if isinstance(u.content, dict) else str(u.content)
            self.vector_db.upsert(
                u.id,
                summary,
                {
                    "source": u.source,
                    "confidence": u.confidence,
                    "conflict_count": len(u.conflict_ids),
                    "topic": u.content.get("topic", "") if isinstance(u.content, dict) else "",
                },
            )
        return {"status": "OK", "metadata": metadata, "ingested": len(result["inserted"]), "skipped": len(result["skipped"]) }

    def run_cognition(self, goal: str, scenario: str) -> Dict[str, Any]:
        judgement = self.loop.run({"goal": goal, "boundary": "global", "metadata": {"scenario": scenario}})
        return {"goal": judgement.goal, "decisions": judgement.decisions, "diagnostics": judgement.diagnostics}

    def retrieve_knowledge(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        from cognitive_os.vector.vector_store import KnowledgeWeightedRetriever

        hits = self.vector_db.search(query, top_k=top_k)
        reranked = KnowledgeWeightedRetriever.rerank(hits)
        return [
            {"id": h.id, "score": round(h.score, 4), "topic": h.metadata.get("topic", ""), "text": h.text[:240]}
            for h in reranked
        ]

    def load_telemetry(self) -> Dict[str, Any]:
        return {
            "documents": self.memory.load_documents(limit=20),
            "judgements": self.memory.load_judgements(limit=10),
            "loop_runs": self.memory.load_loop_runs(limit=10),
        }
