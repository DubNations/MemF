from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FileExtension(Enum):
    PDF = ".pdf"
    DOC = ".doc"
    DOCX = ".docx"
    PPTX = ".pptx"
    TXT = ".txt"
    MD = ".md"
    CSV = ".csv"
    XLSX = ".xlsx"
    HTML = ".html"
    URL = ".url"


class ParseStrategy(Enum):
    AUTO = "auto"
    FAST = "fast"
    HI_RES = "hi_res"


@dataclass(slots=True)
class TableData:
    headers: List[str]
    rows: List[List[str]]
    caption: str = ""

    def to_markdown(self) -> str:
        if not self.headers or not self.rows:
            return ""
        lines = ["| " + " | ".join(self.headers) + " |"]
        lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        for row in self.rows:
            lines.append("| " + " | ".join(row) + " |")
        if self.caption:
            lines.append(f"\n*{self.caption}*")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headers": self.headers,
            "rows": self.rows,
            "caption": self.caption,
        }


@dataclass(slots=True)
class ParseResult:
    text: str
    tables: List[TableData] = field(default_factory=list)
    images: List[bytes] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    pages: int = 1
    strategy_used: ParseStrategy = ParseStrategy.AUTO
    ocr_used: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.text.strip())

    def to_knowledge_content(self) -> Dict[str, Any]:
        content: Dict[str, Any] = {
            "text": self.text,
            "tables": [t.to_dict() for t in self.tables],
            "page_count": self.pages,
            "ocr_used": self.ocr_used,
        }
        content.update(self.metadata)
        return content


class BaseParser(ABC):
    supported_extensions: List[FileExtension] = []

    @abstractmethod
    def parse(
        self,
        content: bytes,
        filename: str,
        strategy: ParseStrategy = ParseStrategy.AUTO,
        **kwargs: Any,
    ) -> ParseResult:
        pass

    @abstractmethod
    def parse_from_path(
        self,
        file_path: str,
        strategy: ParseStrategy = ParseStrategy.AUTO,
        **kwargs: Any,
    ) -> ParseResult:
        pass

    def supports_extension(self, ext: str) -> bool:
        try:
            extension = FileExtension(ext.lower())
            return extension in self.supported_extensions
        except ValueError:
            return False

    @staticmethod
    def get_extension(filename: str) -> str:
        idx = filename.rfind(".")
        return filename[idx:].lower() if idx != -1 else ""

    def detect_ocr_need(self, content: bytes, filename: str) -> bool:
        ext = self.get_extension(filename)
        if ext != ".pdf":
            return False
        text_indicators = [b"BT", b"ET", b"Tj", b"TJ", b"stream"]
        has_text = any(indicator in content for indicator in text_indicators)
        image_indicators = [b"Image", b"DCTDecode", b"FlateDecode"]
        has_images = any(indicator in content for indicator in image_indicators)
        return has_images and not has_text
