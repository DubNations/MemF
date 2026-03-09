from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PinnedDocument:
    document_id: int
    filename: str
    knowledge_base_id: Optional[int]
    pinned_at: datetime = field(default_factory=datetime.utcnow)
    pinned_by: Optional[str] = None
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "knowledge_base_id": self.knowledge_base_id,
            "pinned_at": self.pinned_at.isoformat(),
            "pinned_by": self.pinned_by,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class Citation:
    knowledge_unit_id: str
    document_id: Optional[int]
    filename: str
    text_snippet: str
    relevance_score: float
    page_number: Optional[int] = None
    source: str = "private"
    confidence: float = 0.5
    is_pinned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "knowledge_unit_id": self.knowledge_unit_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "text_snippet": self.text_snippet,
            "relevance_score": round(self.relevance_score, 4),
            "page_number": self.page_number,
            "source": self.source,
            "confidence": self.confidence,
            "is_pinned": self.is_pinned,
        }

    def to_markdown(self) -> str:
        score_str = f"({self.relevance_score:.2f})"
        pinned_str = "📌 " if self.is_pinned else ""
        source_icon = {"human_verified": "✓", "private": "🔒", "public": "🌐"}.get(self.source, "")
        return f"{pinned_str}[{self.filename}] {source_icon} {score_str}: {self.text_snippet[:100]}..."


class DocumentPinningManager:
    def __init__(self, db_path: str = "./data/pinned_docs.db"):
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:")
            return self._conn
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pinned_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                knowledge_unit_id TEXT,
                filename TEXT NOT NULL,
                knowledge_base_id INTEGER,
                session_id TEXT,
                pinned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pinned_by TEXT,
                priority INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pinned_session 
            ON pinned_documents(session_id, priority DESC)
        """)
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

    def pin_document(
        self,
        session_id: str,
        document_id: Optional[int] = None,
        knowledge_unit_id: Optional[str] = None,
        filename: str = "",
        knowledge_base_id: Optional[int] = None,
        pinned_by: Optional[str] = None,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PinnedDocument:
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO pinned_documents 
            (document_id, knowledge_unit_id, filename, knowledge_base_id, session_id, pinned_by, priority, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                knowledge_unit_id,
                filename,
                knowledge_base_id,
                session_id,
                pinned_by,
                priority,
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
        if self._db_path != ":memory:":
            conn.close()

        return PinnedDocument(
            document_id=document_id or 0,
            filename=filename,
            knowledge_base_id=knowledge_base_id,
            pinned_by=pinned_by,
            priority=priority,
            metadata=metadata or {},
        )

    def unpin_document(
        self,
        session_id: str,
        document_id: Optional[int] = None,
        knowledge_unit_id: Optional[str] = None,
    ) -> bool:
        conn = self._get_connection()
        if document_id:
            cursor = conn.execute(
                "DELETE FROM pinned_documents WHERE document_id = ? AND session_id = ?",
                (document_id, session_id),
            )
        elif knowledge_unit_id:
            cursor = conn.execute(
                "DELETE FROM pinned_documents WHERE knowledge_unit_id = ? AND session_id = ?",
                (knowledge_unit_id, session_id),
            )
        else:
            cursor = conn.execute(
                "DELETE FROM pinned_documents WHERE session_id = ?",
                (session_id,),
            )
        conn.commit()
        result = cursor.rowcount > 0
        if self._db_path != ":memory:":
            conn.close()
        return result

    def unpin_all(self, session_id: str) -> int:
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM pinned_documents WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        result = cursor.rowcount
        if self._db_path != ":memory:":
            conn.close()
        return result

    def get_session_pins(self, session_id: str) -> List[PinnedDocument]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT * FROM pinned_documents 
            WHERE session_id = ? 
            ORDER BY priority DESC, pinned_at DESC
            """,
            (session_id,),
        )
        results = [
            PinnedDocument(
                document_id=row["document_id"] or 0,
                filename=row["filename"],
                knowledge_base_id=row["knowledge_base_id"],
                pinned_at=datetime.fromisoformat(row["pinned_at"]) if row["pinned_at"] else datetime.utcnow(),
                pinned_by=row["pinned_by"],
                priority=row["priority"],
                metadata=json.loads(row["metadata"] or "{}"),
            )
            for row in cursor.fetchall()
        ]
        if self._db_path != ":memory:":
            conn.close()
        return results

    def get_pinned_documents(self, session_id: str) -> List[PinnedDocument]:
        return self.get_session_pins(session_id)

    def is_pinned(self, document_id: int, session_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM pinned_documents WHERE document_id = ? AND session_id = ?",
            (document_id, session_id),
        )
        result = cursor.fetchone() is not None
        if self._db_path != ":memory:":
            conn.close()
        return result


class CitationManager:
    def __init__(self, pinning_manager: Optional[DocumentPinningManager] = None):
        self._pinning_manager = pinning_manager
        self.citations: List[Citation] = []

    def add_citation(self, citation: Citation) -> None:
        self.citations.append(citation)

    def clear(self) -> None:
        self.citations = []

    def get_citations(self) -> List[Citation]:
        return self.citations

    def build_citations(
        self,
        retrieved: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        max_citations: int = 10,
    ) -> List[Citation]:
        citations = []
        pinned_ids = set()

        if self._pinning_manager and session_id:
            pinned_docs = self._pinning_manager.get_pinned_documents(session_id)
            pinned_ids = {p.document_id for p in pinned_docs}

        for item in retrieved[:max_citations]:
            doc_id = item.get("document_id")
            filename = item.get("filename", "Unknown")
            text = item.get("text", "")
            score = item.get("score", 0.5)
            source = item.get("source", "private")
            confidence = item.get("confidence", 0.5)

            is_pinned = doc_id in pinned_ids if doc_id else False

            citations.append(
                Citation(
                    knowledge_unit_id=item.get("id", ""),
                    document_id=doc_id,
                    filename=filename,
                    text_snippet=text[:200] if text else "",
                    relevance_score=score,
                    page_number=item.get("page_number"),
                    source=source,
                    confidence=confidence,
                    is_pinned=is_pinned,
                )
            )

        citations.sort(key=lambda c: (not c.is_pinned, -c.relevance_score))
        self.citations = citations

        return citations

    def format_citations(self) -> str:
        return self.format_citations_markdown(self.citations)

    def format_citations_markdown(self, citations: List[Citation]) -> str:
        if not citations:
            return "No citations available."

        lines = ["## Sources", ""]
        for i, citation in enumerate(citations, 1):
            pinned_marker = "📌 " if citation.is_pinned else ""
            source_icon = {"human_verified": "✓", "private": "🔒", "public": "🌐"}.get(
                citation.source, ""
            )
            lines.append(
                f"{i}. {pinned_marker}**{citation.filename}** {source_icon} "
                f"(relevance: {citation.relevance_score:.2f}, confidence: {citation.confidence:.2f})"
            )
            if citation.text_snippet:
                lines.append(f"   > {citation.text_snippet[:150]}...")
            lines.append("")

        return "\n".join(lines)

    def format_citations_inline(self, citations: List[Citation]) -> str:
        if not citations:
            return ""

        parts = []
        for citation in citations[:5]:
            pinned_marker = "📌" if citation.is_pinned else ""
            parts.append(f"[{citation.filename}{pinned_marker}]")

        return " ".join(parts)
