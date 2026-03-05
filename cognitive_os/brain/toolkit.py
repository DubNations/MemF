from __future__ import annotations

import base64
import re
from dataclasses import asdict
from typing import Any, Dict, List

from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.ingestion.document_pipeline import DocumentPipeline
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.vector.vector_store import LocalVectorDB


class BrainToolkit:
    MAX_UPLOAD_BYTES = 150 * 1024 * 1024
    ALLOWED_MIME = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    def __init__(self, memory: MemoryPlane, loop: CognitiveLoop, vector_db: LocalVectorDB) -> None:
        self.memory = memory
        self.loop = loop
        self.vector_db = vector_db

    def validate_upload(self, filename: str, mime_type: str, content_base64: str) -> Dict[str, Any]:
        ext_ok = any(filename.lower().endswith(x) for x in [".pdf", ".doc", ".docx"])
        if not ext_ok:
            return {"ok": False, "code": "INVALID_FORMAT", "message": "Only DOC/DOCX/PDF are supported"}

        if mime_type and mime_type not in self.ALLOWED_MIME:
            return {"ok": False, "code": "INVALID_MIME", "message": f"Unsupported mime_type: {mime_type}"}

        try:
            content = base64.b64decode(content_base64)
        except Exception:
            return {"ok": False, "code": "INVALID_BASE64", "message": "Content is not valid base64"}

        if len(content) > self.MAX_UPLOAD_BYTES:
            return {
                "ok": False,
                "code": "FILE_TOO_LARGE",
                "message": f"File size exceeds 150MB limit: {len(content)} bytes",
            }
        return {"ok": True, "content": content, "size": len(content)}

    def upload_document(
        self,
        filename: str,
        content_base64: str,
        scenario: str,
        source: str = "private",
        mime_type: str = "",
        knowledge_base_id: int | None = None,
    ) -> Dict[str, Any]:
        check = self.validate_upload(filename, mime_type, content_base64)
        if not check["ok"]:
            metadata = {
                "filename": filename,
                "format": filename.split(".")[-1].lower() if "." in filename else "",
                "status": "FAILED",
                "sections": 0,
                "text_length": 0,
                "scenario": scenario,
                "message": check["code"],
                "knowledge_base_id": knowledge_base_id,
                "mime_type": mime_type,
                "file_size_bytes": 0,
            }
            self.memory.save_document_record(metadata)
            return {"status": "FAILED", "metadata": metadata, "ingested": 0, "error": check}

        parse_result, text = DocumentPipeline.parse_base64_document(filename, content_base64)
        metadata = DocumentPipeline.map_document_metadata(parse_result, scenario)
        metadata["knowledge_base_id"] = knowledge_base_id
        metadata["mime_type"] = mime_type
        metadata["file_size_bytes"] = check["size"]
        document_id = self.memory.save_document_record(metadata)

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
                    "knowledge_base_id": knowledge_base_id,
                    "document_id": document_id,
                    "filename": filename,
                },
            )
        return {
            "status": "OK",
            "metadata": metadata,
            "document_id": document_id,
            "ingested": len(result["inserted"]),
            "skipped": len(result["skipped"]),
        }

    def run_cognition(self, goal: str, scenario: str) -> Dict[str, Any]:
        judgement = self.loop.run({"goal": goal, "boundary": "global", "metadata": {"scenario": scenario}})
        return {"goal": judgement.goal, "decisions": judgement.decisions, "diagnostics": judgement.diagnostics}

    def retrieve_knowledge(self, query: str, top_k: int = 8, knowledge_base_id: int | None = None) -> List[Dict[str, Any]]:
        from cognitive_os.vector.vector_store import KnowledgeWeightedRetriever

        hits = self.vector_db.search(query, top_k=max(top_k, 20))
        if knowledge_base_id is not None:
            hits = [h for h in hits if int(h.metadata.get("knowledge_base_id") or 0) == int(knowledge_base_id)]

        # hybrid rerank: vector + keyword overlap
        keywords = set(re.findall(r"\w+", query.lower()))
        enhanced = []
        for h in hits:
            text_words = set(re.findall(r"\w+", h.text.lower()))
            overlap = len(keywords.intersection(text_words)) / max(1, len(keywords))
            h.score = h.score + overlap * 0.15
            enhanced.append(h)

        reranked = KnowledgeWeightedRetriever.rerank(enhanced)[:top_k]
        return [
            {
                "id": h.id,
                "score": round(h.score, 4),
                "topic": h.metadata.get("topic", ""),
                "document_id": h.metadata.get("document_id"),
                "filename": h.metadata.get("filename", ""),
                "knowledge_base_id": h.metadata.get("knowledge_base_id"),
                "text": h.text[:320],
            }
            for h in reranked
        ]

    def load_telemetry(self) -> Dict[str, Any]:
        return {
            "documents": self.memory.load_documents(limit=20),
            "judgements": self.memory.load_judgements(limit=10),
            "loop_runs": self.memory.load_loop_runs(limit=10),
        }
