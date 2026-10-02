"""Building blocks for the demo documents: what a document consists of.

The demo documents are written for the demo organizations; they are
fictional and contain no data of real people or companies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Style(StrEnum):
    TITLE = "title"
    SUBTITLE = "subtitle"
    HEADING = "heading"
    BODY = "body"
    CLAUSE = "clause"
    BULLET = "bullet"
    NUMBERED = "numbered"
    RIGHT = "right"
    CENTER = "center"
    PLAIN = "plain"
    SIGNATURE = "signature"


@dataclass(frozen=True, slots=True)
class Para:
    text: str
    style: Style = Style.BODY


@dataclass(frozen=True, slots=True)
class Table:
    rows: tuple[tuple[str, ...], ...]
    header: bool = True
    borders: bool = True


@dataclass(frozen=True, slots=True)
class PageBreak:
    pass


Element = Para | Table | PageBreak


@dataclass(frozen=True, slots=True)
class PageSetup:
    """Margins in millimetres, fonts in points."""

    margin_top: float = 20
    margin_bottom: float = 20
    margin_left: float = 30
    margin_right: float = 15
    font: str = "Times New Roman"
    size: float = 14
    line_spacing: float = 1.0
    first_line_indent: float = 12.5


@dataclass(frozen=True, slots=True)
class DemoDocument:
    """One file of the demo set and how it is produced."""

    path: str
    elements: tuple[Element, ...]
    page: PageSetup = field(default_factory=PageSetup)
    # docx | pdf (converted from the DOCX) | scan (PDF of page images)
    output: str = "docx"


def paras(style: Style, *texts: str) -> tuple[Para, ...]:
    return tuple(Para(text, style) for text in texts)
