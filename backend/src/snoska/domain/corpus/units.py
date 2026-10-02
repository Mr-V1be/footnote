from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class UnitKind(StrEnum):
    """Levels of a Russian federal law, from the outermost."""

    CHAPTER = "chapter"
    ARTICLE = "article"
    PART = "part"
    CLAUSE = "clause"
    SUBCLAUSE = "subclause"
    PARAGRAPH = "paragraph"


@dataclass(frozen=True, slots=True)
class ParsedUnit:
    """A unit as read from a source, before it is stored."""

    kind: UnitKind
    number: str | None
    heading: str | None
    text: str
    notes: tuple[str, ...] = ()
    repealed: bool = False
    children: tuple[ParsedUnit, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class NormUnit:
    """A stored unit of an edition.

    ``anchor`` identifies the same provision across editions (``st-18.1/ch-1``),
    so citations stay valid when the law is amended.
    """

    id: UUID
    edition_id: UUID
    parent_id: UUID | None
    ordinal: int
    depth: int
    kind: UnitKind
    number: str | None
    anchor: str
    citation: str
    heading: str | None
    text: str
    notes: tuple[str, ...]
    repealed: bool
    embedding_sha256: str | None
