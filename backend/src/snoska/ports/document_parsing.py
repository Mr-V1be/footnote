from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from snoska.domain.documents.structure import Block, DocumentLayout
from snoska.domain.documents.version import ExtractionMethod, ParseFailureCode


class DocumentParseError(Exception):
    """The file itself cannot be parsed. Retrying will not help."""

    def __init__(self, code: ParseFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    blocks: tuple[Block, ...]
    layout: DocumentLayout
    method: ExtractionMethod
    page_count: int | None
    ocr_confidence: float | None


class DocumentParser(Protocol):
    format_code: str

    async def parse(self, content: bytes) -> ParsedDocument: ...


class DocumentParserRegistry(Protocol):
    def for_format(self, format_code: str) -> DocumentParser: ...
