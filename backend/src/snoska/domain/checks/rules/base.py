from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from snoska.domain.checks.catalog import CatalogError
from snoska.domain.checks.outcome import (
    CheckOutcome,
    Detail,
    FindingDraft,
    FindingKind,
    TextLocation,
)
from snoska.domain.documents.structure import Alignment, Block, BlockKind, DocumentStructure

# Body text: what a reader reads as running text. Short lines (requisites,
# signatures, captions) and centred or right-aligned blocks are layout, not body.
BODY_MIN_CHARS = 60
BODY_KINDS = frozenset({BlockKind.PARAGRAPH, BlockKind.LIST_ITEM})
# Up to this many places get a marker each; beyond it the problem is
# document-wide and one finding at the first place says how many there are.
MAX_MARKED_PLACES = 5


class RuleParams:
    """Typed access to a rule's parameters from the catalogue."""

    def __init__(self, check_code: str, values: Mapping[str, object]) -> None:
        self._code = check_code
        self._values = values

    def number(self, name: str) -> float:
        value = self._values.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise CatalogError(f"{self._code}: parameter {name!r} must be a number")
        return float(value)

    def text(self, name: str) -> str:
        value = self._values.get(name)
        if not isinstance(value, str) or not value:
            raise CatalogError(f"{self._code}: parameter {name!r} must be a non-empty string")
        return value

    def texts(self, name: str) -> tuple[str, ...]:
        value = self._values.get(name)
        if not isinstance(value, list | tuple) or not all(isinstance(item, str) for item in value):
            raise CatalogError(f"{self._code}: parameter {name!r} must be a list of strings")
        return tuple(str(item) for item in value)


class Rule(Protocol):
    """A deterministic check strategy. Rules are pure: same structure, same verdict."""

    id: str

    def validate(self, params: RuleParams) -> None:
        """Raise CatalogError when the parameters are unusable."""
        ...

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome: ...


@dataclass(frozen=True, slots=True)
class Offence:
    """A place that breaks a rule and how."""

    block: Block
    detail: Detail
    location: TextLocation | None = None


def is_body(block: Block) -> bool:
    if block.kind not in BODY_KINDS or len(block.text) < BODY_MIN_CHARS:
        return False
    alignment = block.paragraph.alignment if block.paragraph else None
    return alignment not in (Alignment.CENTER, Alignment.RIGHT)


def body_blocks(structure: DocumentStructure) -> list[Block]:
    return [block for block in structure.blocks if is_body(block)]


def whole_block(block: Block) -> TextLocation:
    return TextLocation(block.ordinal, 0, len(block.text))


def offences_outcome(offences: Iterable[Offence], widespread: Detail) -> CheckOutcome:
    """A finding per offending place, or one finding when the problem is everywhere.

    ``widespread`` describes the document-wide case; it receives the number
    of places as the ``count`` parameter.
    """
    listed = list(offences)
    if not listed:
        return CheckOutcome.passed()
    if len(listed) > MAX_MARKED_PLACES:
        first = listed[0]
        detail = Detail.message(
            widespread.code or "", **{**widespread.params, "count": len(listed)}
        )
        return CheckOutcome.violation(
            FindingDraft(
                kind=FindingKind.VIOLATION,
                detail=detail,
                location=first.location or whole_block(first.block),
            )
        )
    return CheckOutcome.violation(
        *(
            FindingDraft(
                kind=FindingKind.VIOLATION,
                detail=offence.detail,
                location=offence.location or whole_block(offence.block),
            )
            for offence in listed
        )
    )
