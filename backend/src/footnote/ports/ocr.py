from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OcrLine:
    text: str
    left: float
    top: float
    right: float
    bottom: float
    height: float
    confidence: float


@dataclass(frozen=True, slots=True)
class OcrPage:
    """Recognised text of one page image; coordinates in image pixels."""

    width: float
    height: float
    dpi: int
    lines: tuple[OcrLine, ...]


class OcrEngine(Protocol):
    async def recognize(self, image_png: bytes, *, dpi: int) -> OcrPage: ...
