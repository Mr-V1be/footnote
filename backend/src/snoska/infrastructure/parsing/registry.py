from __future__ import annotations

from collections.abc import Iterable

from snoska.domain.documents.formats import UnsupportedFormatError
from snoska.ports.document_parsing import DocumentParser


class ParserRegistry:
    """Maps a document format to its parser; a new format is a new entry."""

    def __init__(self, parsers: Iterable[DocumentParser]) -> None:
        self._parsers = {parser.format_code: parser for parser in parsers}

    def for_format(self, format_code: str) -> DocumentParser:
        parser = self._parsers.get(format_code)
        if parser is None:
            raise UnsupportedFormatError(f"no parser for format {format_code!r}")
        return parser
