from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from cognitive_os.ingestion.parsers import MegaparseAdapter, NativeParser
from cognitive_os.ingestion.parsers.base_parser import BaseParser, ParseResult, ParseStrategy
from cognitive_os.ontology.ontology_entity import KnowledgeUnit


@dataclass(slots=True)
class DocumentParseResult:
    filename: str
    format: str
    status: str
    pages_or_sections: int
    text_length: int
    tables_count: int = 0
    ocr_used: bool = False
    message: str = ""


class DocumentPipeline:
    supported_extensions = {".pdf", ".doc", ".docx", ".pptx", ".txt", ".md", ".csv", ".xlsx"}

    def __init__(
        self,
        parser: Optional[BaseParser] = None,
        use_megaparse: bool = True,
        enable_ocr: bool = True,
        enable_table_extraction: bool = True,
        ocr_language: str = "chi_sim+eng",
    ):
        if parser is not None:
            self._parser = parser
        elif use_megaparse:
            self._parser = MegaparseAdapter(
                enable_ocr=enable_ocr,
                enable_table_extraction=enable_table_extraction,
                ocr_language=ocr_language,
            )
        else:
            self._parser = NativeParser()

    @classmethod
    def parse_base64_document(
        cls,
        filename: str,
        content_base64: str,
        strategy: ParseStrategy = ParseStrategy.AUTO,
        parser: Optional[BaseParser] = None,
    ) -> Tuple[DocumentParseResult, str]:
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
                DocumentParseResult(filename, ext, "FAILED", 0, 0, message="invalid_base64"),
                "",
            )

        pipeline = cls(parser=parser)
        return pipeline.parse_document(content, filename, strategy)

    def parse_document(
        self,
        content: bytes,
        filename: str,
        strategy: ParseStrategy = ParseStrategy.AUTO,
    ) -> Tuple[DocumentParseResult, str]:
        ext = self._ext(filename)

        result = self._parser.parse(content, filename, strategy)

        if not result.success:
            return (
                DocumentParseResult(
                    filename=filename,
                    format=ext,
                    status="FAILED",
                    pages_or_sections=0,
                    text_length=0,
                    message=result.error or "empty_or_unreadable_content",
                ),
                "",
            )

        text_with_tables = result.text
        if result.tables:
            table_texts = [t.to_markdown() for t in result.tables if t.to_markdown()]
            if table_texts:
                text_with_tables = result.text + "\n\n" + "\n\n".join(table_texts)

        doc_result = DocumentParseResult(
            filename=filename,
            format=ext,
            status="OK",
            pages_or_sections=result.pages,
            text_length=len(text_with_tables),
            tables_count=len(result.tables),
            ocr_used=result.ocr_used,
        )
        return doc_result, text_with_tables

    @classmethod
    def to_knowledge_units(
        cls,
        filename: str,
        raw_text: str,
        scenario: str,
        source: str = "private",
        chunk_size: int = 800,
        tables_count: int = 0,
        ocr_used: bool = False,
    ) -> List[KnowledgeUnit]:
        import time
        current_time = time.time()
        
        chunks = [raw_text[i : i + chunk_size] for i in range(0, len(raw_text), chunk_size)]
        units: List[KnowledgeUnit] = []

        base_confidence = 0.62
        if ocr_used:
            base_confidence = 0.55
        if tables_count > 0:
            base_confidence = min(0.70, base_confidence + 0.05)

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
                        "tables_count": tables_count,
                        "ocr_used": ocr_used,
                    },
                    source=source,
                    confidence=base_confidence,
                    valid_boundary="global",
                    created_at=current_time,
                    last_used_at=current_time,
                    use_count=0,
                )
            )
        return units

    @classmethod
    def to_knowledge_units_from_result(
        cls,
        result: DocumentParseResult,
        raw_text: str,
        scenario: str,
        source: str = "private",
        chunk_size: int = 800,
    ) -> List[KnowledgeUnit]:
        return cls.to_knowledge_units(
            filename=result.filename,
            raw_text=raw_text,
            scenario=scenario,
            source=source,
            chunk_size=chunk_size,
            tables_count=result.tables_count,
            ocr_used=result.ocr_used,
        )

    @staticmethod
    def map_document_metadata(result: DocumentParseResult, scenario: str) -> Dict[str, Any]:
        return {
            "filename": result.filename,
            "format": result.format,
            "status": result.status,
            "sections": result.pages_or_sections,
            "text_length": result.text_length,
            "tables_count": result.tables_count,
            "ocr_used": result.ocr_used,
            "scenario": scenario,
            "message": result.message,
        }

    @staticmethod
    def _ext(filename: str) -> str:
        idx = filename.rfind(".")
        return filename[idx:].lower() if idx != -1 else ""
