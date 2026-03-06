from __future__ import annotations

import base64
import io
import re
import zipfile
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from xml.etree import ElementTree

from cognitive_os.ontology.ontology_entity import KnowledgeUnit


@dataclass(slots=True)
class DocumentParseResult:
    filename: str
    format: str
    status: str
    pages_or_sections: int
    text_length: int
    message: str = ""


class DocumentPipeline:
    supported_extensions = {".pdf", ".doc", ".docx"}

    @classmethod
    def parse_base64_document(cls, filename: str, content_base64: str) -> Tuple[DocumentParseResult, str]:
        ext = cls._ext(filename)
        if ext not in cls.supported_extensions:
            return (
                DocumentParseResult(
                    filename=filename,
                    format=ext,
                    status="FAILED",
                    pages_or_sections=0,
                    text_length=0,
                    message="unsupported_format",
                ),
                "",
            )

        try:
            content = base64.b64decode(content_base64)
        except Exception:
            return (
                DocumentParseResult(filename, ext, "FAILED", 0, 0, "invalid_base64"),
                "",
            )

        if ext == ".pdf":
            text = cls._parse_pdf(content)
        elif ext == ".docx":
            text = cls._parse_docx(content)
        else:
            text = cls._parse_doc_binary(content)

        if not text.strip():
            return (
                DocumentParseResult(filename, ext, "FAILED", 0, 0, "empty_or_unreadable_content"),
                "",
            )

        sections = max(1, len([x for x in text.split("\n") if x.strip()]))
        result = DocumentParseResult(
            filename=filename,
            format=ext,
            status="OK",
            pages_or_sections=sections,
            text_length=len(text),
        )
        return result, text

    @classmethod
    def to_knowledge_units(
        cls,
        filename: str,
        raw_text: str,
        scenario: str,
        source: str = "private",
        chunk_size: int = 800,
    ) -> List[KnowledgeUnit]:
        chunks = [raw_text[i : i + chunk_size] for i in range(0, len(raw_text), chunk_size)]
        units: List[KnowledgeUnit] = []
        for i, chunk in enumerate(chunks):
            units.append(
                KnowledgeUnit(
                    id=f"doc_{filename}_{i}",
                    knowledge_type="case",
                    content={
                        "topic": scenario,
                        "polarity": "pro",
                        "summary": chunk.strip(),
                        "document": filename,
                        "section_index": i,
                        "reinforcement": 0.02,
                    },
                    source=source,
                    confidence=0.62,
                    valid_boundary="global",
                )
            )
        return units

    @staticmethod
    def map_document_metadata(result: DocumentParseResult, scenario: str) -> Dict[str, Any]:
        return {
            "filename": result.filename,
            "format": result.format,
            "status": result.status,
            "sections": result.pages_or_sections,
            "text_length": result.text_length,
            "scenario": scenario,
            "message": result.message,
        }

    @staticmethod
    def _ext(filename: str) -> str:
        idx = filename.rfind(".")
        return filename[idx:].lower() if idx != -1 else ""

    @staticmethod
    def _parse_docx(content: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                data = zf.read("word/document.xml")
            root = ElementTree.fromstring(data)
            text_nodes = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
            return "\n".join(text_nodes)
        except Exception:
            return ""

    @staticmethod
    def _parse_pdf(content: bytes) -> str:
        # Lightweight extraction: pull text fragments from PDF stream literals.
        # Works for many text PDFs and fails safely for scanned/image PDFs.
        text_fragments = re.findall(rb"\(([^\)]{1,500})\)\s*Tj", content)
        if not text_fragments:
            text_fragments = re.findall(rb"\[(.*?)\]\s*TJ", content, flags=re.S)
        parts: List[str] = []
        for frag in text_fragments:
            try:
                cleaned = frag.replace(b"\\n", b" ").replace(b"\\r", b" ")
                parts.append(cleaned.decode("latin-1", errors="ignore"))
            except Exception:
                continue
        return "\n".join([p.strip() for p in parts if p.strip()])

    @staticmethod
    def _parse_doc_binary(content: bytes) -> str:
        # Legacy .doc fallback parser (best-effort): strip control bytes.
        # For advanced fidelity, plug in antiword/libreoffice in future iterations.
        text = content.decode("latin-1", errors="ignore")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
