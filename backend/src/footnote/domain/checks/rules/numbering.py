from __future__ import annotations

import re

from footnote.domain.checks.catalog import CatalogError
from footnote.domain.checks.outcome import CheckOutcome, Detail
from footnote.domain.checks.rules.base import Offence, RuleParams, offences_outcome
from footnote.domain.documents.structure import Block, BlockKind, DocumentStructure

_ARABIC = re.compile(r"^(\d+(?:\.\d+)*)\.?$")
_ROMAN = re.compile(r"^[IVXLC]+\.?$")
_NUMBERED_KINDS = frozenset({BlockKind.HEADING, BlockKind.LIST_ITEM})


def _numbered(structure: DocumentStructure) -> list[tuple[Block, str]]:
    return [
        (block, block.label.strip())
        for block in structure.blocks
        if block.kind in _NUMBERED_KINDS and block.label and block.label.strip()
    ]


def _arabic_path(label: str) -> tuple[int, ...] | None:
    match = _ARABIC.match(label)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


class ArabicNumberingRule:
    """Sections and points are numbered with Arabic numerals, at most N levels deep."""

    id = "numbering_arabic"

    def validate(self, params: RuleParams) -> None:
        if params.number("max_levels") < 1:
            raise CatalogError("max_levels must be at least 1")

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        numbered = _numbered(structure)
        if not numbered:
            return CheckOutcome.not_applicable()
        max_levels = int(params.number("max_levels"))
        offences: list[Offence] = []
        for block, label in numbered:
            if _ROMAN.match(label):
                offences.append(Offence(block, Detail.message("numbering_roman", label=label)))
                continue
            path = _arabic_path(label)
            if path is not None and len(path) > max_levels:
                offences.append(
                    Offence(
                        block,
                        Detail.message(
                            "numbering_depth", label=label, levels=len(path), max=max_levels
                        ),
                    )
                )
        return offences_outcome(
            offences, len(numbered), Detail.message("numbering_roman_widespread"), params
        )


class NumberingSequenceRule:
    """Numbers follow each other without gaps or repeats within a level."""

    id = "numbering_sequence"

    def validate(self, params: RuleParams) -> None:
        return None

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        paths = [
            (block, label, path)
            for block, label in _numbered(structure)
            if (path := _arabic_path(label)) is not None
        ]
        if len(paths) < 2:
            return CheckOutcome.not_applicable()
        # The last number seen in each scope. Headings and dotted points
        # (2, 1.1, 1.2.3) form the document's outline; a plain list of points
        # under a heading (1. 2. 3.) is a list of its own.
        last: dict[tuple[object, tuple[int, ...]], int] = {}
        offences: list[Offence] = []
        section = -1
        for block, label, path in paths:
            if block.kind is BlockKind.HEADING:
                section = block.ordinal
            in_list = block.kind is BlockKind.LIST_ITEM and len(path) == 1
            scope: object = ("list", section) if in_list else "outline"
            parent, number = path[:-1], path[-1]
            expected = last.get((scope, parent), 0) + 1
            # Numbering back at 1 starts a new list, which is legitimate.
            if number not in (expected, 1):
                offences.append(
                    Offence(
                        block,
                        Detail.message(
                            "numbering_gap",
                            label=label,
                            expected=".".join(str(part) for part in (*parent, expected)),
                        ),
                    )
                )
            last[(scope, parent)] = number
        return offences_outcome(
            offences, len(paths), Detail.message("numbering_gap_widespread"), params
        )
