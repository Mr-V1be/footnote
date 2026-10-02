"""Deterministic formatting rules over parsed structures."""

from __future__ import annotations

from snoska.domain.checks.outcome import ResultStatus
from snoska.domain.checks.rules.base import MAX_MARKED_PLACES, RuleParams
from snoska.domain.checks.rules.registry import DEFAULT_RULES
from snoska.domain.documents.structure import (
    Alignment,
    Block,
    BlockKind,
    DocumentLayout,
    DocumentStructure,
    FontUsage,
    LayoutSource,
    PageSetup,
    ParagraphFormat,
    Requisite,
    RequisiteKind,
)

BODY = "Оператор обрабатывает персональные данные в целях исполнения трудовых договоров."


def evaluate(rule: str, structure: DocumentStructure, **params: object):  # type: ignore[no-untyped-def]
    return DEFAULT_RULES.get(rule).evaluate(structure, RuleParams(rule, params))


def body(ordinal: int, *, size: float = 14, spacing: float = 1.0, indent: float = 12.5) -> Block:
    return Block(
        ordinal=ordinal,
        kind=BlockKind.PARAGRAPH,
        text=BODY,
        fonts=(FontUsage("Times New Roman", size, False, False, len(BODY)),),
        paragraph=ParagraphFormat(
            alignment=Alignment.JUSTIFY, first_line_indent_mm=indent, line_spacing=spacing
        ),
    )


def numbered(ordinal: int, label: str, kind: BlockKind = BlockKind.HEADING) -> Block:
    return Block(ordinal=ordinal, kind=kind, text="Раздел", label=label, level=1)


def test_margins_report_each_narrow_side_against_the_minimum() -> None:
    page = PageSetup(LayoutSource.DECLARED, 210, 297, 20, 20, 15, 10)
    outcome = evaluate(
        "page_margins",
        DocumentStructure(blocks=(), layout=DocumentLayout(pages=(page,))),
        min_left_mm=20,
        min_right_mm=10,
        min_top_mm=20,
        min_bottom_mm=20,
        tolerance_mm=0.5,
    )
    assert outcome.status is ResultStatus.VIOLATION
    [finding] = outcome.findings
    assert finding.detail.params["side"] == "left"
    assert finding.location is None, "margins concern the whole document"


def test_font_size_marks_each_place_or_counts_them_when_everywhere() -> None:
    few = DocumentStructure(blocks=(body(0), body(1, size=11)))
    outcome = evaluate("body_font_size", few, min_pt=12, max_pt=14)
    assert [f.location.block_ordinal for f in outcome.findings if f.location] == [1]

    everywhere = DocumentStructure(blocks=tuple(body(i, size=10) for i in range(8)))
    outcome = evaluate("body_font_size", everywhere, min_pt=12, max_pt=14)
    [finding] = outcome.findings
    assert finding.detail.code == "font_size_widespread"
    assert finding.detail.params["count"] == 8 > MAX_MARKED_PLACES


def test_scan_without_font_data_is_not_judged() -> None:
    scan = DocumentStructure(blocks=(Block(0, BlockKind.PARAGRAPH, BODY),))
    assert evaluate("body_font_size", scan, min_pt=12, max_pt=14).status is (
        ResultStatus.NOT_APPLICABLE
    )


def test_line_spacing_and_indent_follow_their_ranges() -> None:
    structure = DocumentStructure(blocks=(body(0), body(1, spacing=2.0, indent=5)))
    spacing = evaluate("line_spacing", structure, min=1.0, max=1.5)
    indent = evaluate("paragraph_indent", structure, indent_mm=12.5, tolerance_mm=1)
    assert [f.detail.params for f in spacing.findings] == [{"value": 2.0}]
    assert [f.detail.params for f in indent.findings] == [{"cm": 0.5}]


def test_missing_requisite_and_signature_order() -> None:
    signature = Requisite(RequisiteKind.SIGNATURE, 3, 0, 13, "Ковалёва А.С.")
    structure = DocumentStructure(blocks=(), requisites=(signature,))
    missing = evaluate("requisite_present", structure, requisite="date")
    assert missing.findings[0].detail.params == {"requisite": "date"}
    order = evaluate("signature_initials_first", structure)
    assert order.status is ResultStatus.VIOLATION
    assert order.findings[0].location is not None


def test_dates_in_a_non_standard_form_are_reported_but_clause_numbers_are_not() -> None:
    text = "Утверждено 1.2.2026, изменено 2026-03-15; см. ГОСТ Р 7.0.97-2016 и п. 5.1.10."
    structure = DocumentStructure(blocks=(Block(0, BlockKind.PARAGRAPH, text),))
    outcome = evaluate("date_format", structure)
    assert [f.detail.params["value"] for f in outcome.findings] == ["1.2.2026", "2026-03-15"]


def test_numbering_is_arabic_and_at_most_four_levels() -> None:
    structure = DocumentStructure(
        blocks=(numbered(0, "II."), numbered(1, "1.2.3.4.5.", BlockKind.LIST_ITEM))
    )
    outcome = evaluate("numbering_arabic", structure, max_levels=4)
    assert [f.detail.code for f in outcome.findings] == ["numbering_roman", "numbering_depth"]


def test_a_list_inside_a_section_does_not_break_the_section_sequence() -> None:
    structure = DocumentStructure(
        blocks=(
            numbered(0, "1."),
            numbered(1, "2."),
            numbered(2, "1.", BlockKind.LIST_ITEM),
            numbered(3, "2.", BlockKind.LIST_ITEM),
            numbered(4, "3."),
            numbered(5, "3.1.", BlockKind.LIST_ITEM),
            numbered(6, "3.3.", BlockKind.LIST_ITEM),
        )
    )
    outcome = evaluate("numbering_sequence", structure)
    assert [f.detail.params for f in outcome.findings] == [{"label": "3.3.", "expected": "3.2"}]
