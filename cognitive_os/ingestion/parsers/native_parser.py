from __future__ import annotations

import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree

from cognitive_os.ingestion.parsers.base_parser import (
    BaseParser,
    FileExtension,
    ParseResult,
    ParseStrategy,
)


class NativeParser(BaseParser):
    supported_extensions = [
        FileExtension.PDF,
        FileExtension.DOC,
        FileExtension.DOCX,
        FileExtension.TXT,
        FileExtension.MD,
    ]

    def parse(
        self,
        content: bytes,
        filename: str,
        strategy: ParseStrategy = ParseStrategy.AUTO,
        **kwargs: Any,
    ) -> ParseResult:
        ext = self.get_extension(filename)

        if ext == ".pdf":
            return self._parse_pdf(content, filename, strategy)
        elif ext == ".docx":
            return self._parse_docx(content, filename)
        elif ext == ".doc":
            return self._parse_doc(content, filename)
        elif ext in (".txt", ".md"):
            return self._parse_text(content, filename)
        else:
            return ParseResult(
                text="",
                error=f"Unsupported format: {ext}",
                metadata={"filename": filename},
            )

    def parse_from_path(
        self,
        file_path: str,
        strategy: ParseStrategy = ParseStrategy.AUTO,
        **kwargs: Any,
    ) -> ParseResult:
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            filename = file_path.split("/")[-1].split("\\")[-1]
            return self.parse(content, filename, strategy, **kwargs)
        except Exception as e:
            return ParseResult(
                text="",
                error=str(e),
                metadata={"file_path": file_path},
            )

    def _parse_pdf(
        self,
        content: bytes,
        filename: str,
        strategy: ParseStrategy = ParseStrategy.AUTO,
    ) -> ParseResult:
        text_fragments = re.findall(rb"\(([^\)]{1,500})\)\s*Tj", content)
        if not text_fragments:
            text_fragments = re.findall(rb"\[(.*?)\]\s*TJ", content, flags=re.S)

        parts = []
        for frag in text_fragments:
            try:
                cleaned = frag.replace(b"\\n", b" ").replace(b"\\r", b" ")
                parts.append(cleaned.decode("latin-1", errors="ignore"))
            except Exception:
                continue

        text = "\n".join([p.strip() for p in parts if p.strip()])
        ocr_needed = self.detect_ocr_need(content, filename)

        return ParseResult(
            text=text,
            pages=self._estimate_pdf_pages(content),
            strategy_used=ParseStrategy.FAST,
            ocr_used=False,
            metadata={
                "filename": filename,
                "ocr_recommended": ocr_needed and not text.strip(),
            },
        )

    def _parse_docx(self, content: bytes, filename: str) -> ParseResult:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                data = zf.read("word/document.xml")
            root = ElementTree.fromstring(data)
            text_nodes = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
            text = "\n".join(text_nodes)

            return ParseResult(
                text=text,
                pages=1,
                strategy_used=ParseStrategy.FAST,
                metadata={"filename": filename},
            )
        except Exception as e:
            return ParseResult(
                text="",
                error=str(e),
                metadata={"filename": filename},
            )

    def _parse_doc(self, content: bytes, filename: str) -> ParseResult:
        text = content.decode("latin-1", errors="ignore")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        text = re.sub(r"\s+", " ", text)

        return ParseResult(
            text=text.strip(),
            pages=1,
            strategy_used=ParseStrategy.FAST,
            metadata={"filename": filename, "warning": "Legacy .doc format, limited fidelity"},
        )

    def _parse_text(self, content: bytes, filename: str) -> ParseResult:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="ignore")

        return ParseResult(
            text=text,
            pages=len(text.split("\n\n")),
            strategy_used=ParseStrategy.FAST,
            metadata={"filename": filename},
        )

    @staticmethod
    def _estimate_pdf_pages(content: bytes) -> int:
        page_count = content.count(b"/Type /Page") - content.count(b"/Type /Pages")
        return max(1, page_count)
