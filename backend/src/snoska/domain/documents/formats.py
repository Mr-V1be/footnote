from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePath

from snoska.domain.shared.errors import ValidationError


class UnsupportedFormatError(ValidationError):
    code = "unsupported_format"


@dataclass(frozen=True, slots=True)
class DocumentFormat:
    """An accepted upload format.

    A file is accepted only when both its extension and its leading bytes
    agree, so a renamed binary cannot slip through as a document.
    """

    code: str
    media_type: str
    extensions: tuple[str, ...]
    signature: bytes


class FormatRegistry:
    def __init__(self, formats: Iterable[DocumentFormat]) -> None:
        self._formats = {fmt.code: fmt for fmt in formats}

    def get(self, code: str) -> DocumentFormat:
        try:
            return self._formats[code]
        except KeyError as exc:
            raise UnsupportedFormatError(f"unknown format {code!r}") from exc

    def all(self) -> tuple[DocumentFormat, ...]:
        return tuple(self._formats.values())

    @property
    def signature_length(self) -> int:
        return max(len(fmt.signature) for fmt in self._formats.values())

    def detect(self, filename: str, head: bytes) -> DocumentFormat:
        extension = PurePath(filename).suffix.lower()
        for fmt in self._formats.values():
            if extension in fmt.extensions and head.startswith(fmt.signature):
                return fmt
        raise UnsupportedFormatError(f"file {filename!r} is not a supported document")


SUPPORTED_FORMATS = FormatRegistry(
    [
        DocumentFormat(
            code="docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            extensions=(".docx",),
            signature=b"PK\x03\x04",
        ),
        DocumentFormat(
            code="pdf",
            media_type="application/pdf",
            extensions=(".pdf",),
            signature=b"%PDF-",
        ),
    ]
)
