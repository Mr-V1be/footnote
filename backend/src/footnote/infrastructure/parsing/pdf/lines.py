from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from footnote.domain.documents.structure import FontUsage, TableContent

_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
# Style suffixes are separated from the family («Arial-BoldMT», «Calibri,Bold»);
# without the separator «Roman» would be cut from «TimesNewRoman».
_STYLE_SUFFIX = re.compile(
    r"[-,](?:Bold|Italic|Oblique|Regular|Roman|Medium|Semibold|Light)+$",
    re.IGNORECASE,
)
_VENDOR_SUFFIX = re.compile(r"(?:PSMT|PS|MT)$")


@dataclass(frozen=True, slots=True)
class TextLine:
    """A visual line of text on a page; coordinates in points from the top-left."""

    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size_pt: float | None
    fonts: tuple[FontUsage, ...]
    confidence: float | None = None

    @property
    def bold(self) -> bool:
        return bool(self.fonts) and all(font.bold for font in self.fonts)

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class PlacedTable:
    top: float
    bottom: float
    content: TableContent


@dataclass(frozen=True, slots=True)
class PageContent:
    number: int
    width: float
    height: float
    lines: tuple[TextLine, ...]
    tables: tuple[PlacedTable, ...]


@dataclass(frozen=True, slots=True)
class FontName:
    family: str
    bold: bool
    italic: bool


def parse_font_name(raw: str) -> FontName:
    """Split a PDF font name such as ``ABCDEF+TimesNewRomanPS-BoldMT``."""
    name = _SUBSET_PREFIX.sub("", raw)
    lowered = name.lower()
    bold = "bold" in lowered or "black" in lowered or "heavy" in lowered
    italic = "italic" in lowered or "oblique" in lowered
    base = name
    for _ in range(3):
        stripped = _VENDOR_SUFFIX.sub("", _STYLE_SUFFIX.sub("", base))
        if stripped == base:
            break
        base = stripped
    return FontName(family=base or name, bold=bold, italic=italic)


def fonts_of(chars: Iterable[Mapping[str, Any]]) -> tuple[FontUsage, ...]:
    usage: Counter[tuple[str, float, bool, bool]] = Counter()
    for char in chars:
        text = str(char.get("text", ""))
        if not text.strip():
            continue
        font = parse_font_name(str(char.get("fontname", "")))
        size = round(float(char.get("size", 0.0)), 1)
        usage[(font.family, size, font.bold, font.italic)] += 1
    return tuple(
        FontUsage(family=family, size_pt=size, bold=bold, italic=italic, chars=count)
        for (family, size, bold, italic), count in usage.most_common()
    )


def dominant_size(fonts: tuple[FontUsage, ...]) -> float | None:
    return fonts[0].size_pt if fonts else None
