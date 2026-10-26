from __future__ import annotations

from footnote.domain.checks.outcome import CheckOutcome, Detail, FindingDraft, FindingKind
from footnote.domain.checks.rules.base import RuleParams
from footnote.domain.documents.structure import DocumentStructure, LayoutSource, PageSetup

_SIDES = ("left", "right", "top", "bottom")


def _margin(page: PageSetup, side: str) -> float | None:
    value: float | None = getattr(page, f"margin_{side}_mm")
    return value


class PageMarginsRule:
    """Every page keeps margins of at least the given width on each side.

    A DOCX declares its margins; for a PDF they are measured from the edge of
    the page to the printed text, which can only be wider than the declared
    margins, so a measured margin below the minimum is a sure violation.
    """

    id = "page_margins"

    def validate(self, params: RuleParams) -> None:
        for side in _SIDES:
            params.number(f"min_{side}_mm")
        params.number("tolerance_mm")

    def evaluate(self, structure: DocumentStructure, params: RuleParams) -> CheckOutcome:
        pages = structure.layout.pages
        if not pages:
            return CheckOutcome.not_applicable()
        tolerance = params.number("tolerance_mm")
        findings: list[FindingDraft] = []
        for side in _SIDES:
            minimum = params.number(f"min_{side}_mm")
            values = [value for page in pages if (value := _margin(page, side)) is not None]
            if not values:
                continue
            narrowest = min(values)
            if narrowest < minimum - tolerance:
                findings.append(
                    FindingDraft(
                        kind=FindingKind.VIOLATION,
                        detail=Detail.message(
                            "margin",
                            side=side,
                            value=round(narrowest),
                            min=round(minimum),
                            measured=str(
                                all(page.source is LayoutSource.MEASURED for page in pages)
                            ).lower(),
                        ),
                    )
                )
        if not findings:
            return CheckOutcome.passed()
        return CheckOutcome.violation(*findings)
