from __future__ import annotations

import re

from snoska.domain.checks.catalog import CatalogError
from snoska.domain.checks.outcome import (
    CheckOutcome,
    Detail,
    FindingDraft,
    FindingKind,
    TextLocation,
)
from snoska.domain.checks.rules.base import RuleParams
from snoska.domain.documents.structure import DocumentStructure, Requisite, RequisiteKind

_SURNAME_FIRST = re.compile(r"^[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s+[А-ЯЁ]\.\s?(?:[А-ЯЁ]\.)?$")


def _kind(params: RuleParams) -> RequisiteKind:
    code = params.text("requisite")
    try:
        return RequisiteKind(code)
    except ValueError as exc:
        raise CatalogError(f"unknown requisite {code!r}") from exc


def _location(requisite: Requisite) -> TextLocation:
    return TextLocation(requisite.block_ordinal, requisite.start, requisite.end)


def _of_kind(structure: DocumentStructure, kind: RequisiteKind) -> list[Requisite]:
    return [requisite for requisite in structure.requisites if requisite.kind is kind]


class RequisitePresentRule:
    """The document carries a requisite (date, number, title, signature...)."""

    id = "requisite_present"

    def validate(self, params: RuleParams) -> None:
        _kind(params)

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        kind = _kind(params)
        found = _of_kind(structure, kind)
        if found:
            return CheckOutcome.passed(evidence=tuple(_location(item) for item in found[:1]))
        return CheckOutcome.violation(
            FindingDraft(
                kind=FindingKind.VIOLATION,
                detail=Detail.message("requisite_missing", requisite=kind.value),
            )
        )


class SignatureOrderRule:
    """In a signature the initials stand before the surname: «А.С. Ковалёва»."""

    id = "signature_initials_first"

    def validate(self, params: RuleParams) -> None:
        return None

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        signatures = _of_kind(structure, RequisiteKind.SIGNATURE)
        if not signatures:
            return CheckOutcome.not_applicable()
        reversed_names = [item for item in signatures if _SURNAME_FIRST.match(item.value.strip())]
        if not reversed_names:
            return CheckOutcome.passed(evidence=tuple(_location(item) for item in signatures))
        return CheckOutcome.violation(
            *(
                FindingDraft(
                    kind=FindingKind.VIOLATION,
                    detail=Detail.message("signature_order", name=item.value.strip()),
                    location=_location(item),
                )
                for item in reversed_names
            )
        )
