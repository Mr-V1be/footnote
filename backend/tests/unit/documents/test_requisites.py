from __future__ import annotations

from collections.abc import Sequence

from footnote.domain.documents.requisites import RequisiteDetector
from footnote.domain.documents.structure import Block, BlockKind, Requisite, RequisiteKind


def blocks(*texts: str) -> list[Block]:
    return [Block(ordinal=i, kind=BlockKind.PARAGRAPH, text=t) for i, t in enumerate(texts)]


def kinds(found: Sequence[Requisite]) -> dict[RequisiteKind, str]:
    return {r.kind: r.value for r in found}


def test_header_requisites_of_an_order() -> None:
    found = RequisiteDetector().detect(
        blocks(
            "ООО «Полярная звезда»",
            "ПРИКАЗ",
            "14.01.2026\t№ 7-ОД",
            "г. Москва",
            "Об утверждении Политики в отношении обработки персональных данных",
            "В целях выполнения требований закона ПРИКАЗЫВАЮ:",
            "Генеральный директор\tА.С. Ковалёва",
        )
    )
    result = kinds(found)
    assert result[RequisiteKind.ORGANIZATION_NAME] == "ООО «Полярная звезда»"
    assert result[RequisiteKind.DOCUMENT_TYPE] == "ПРИКАЗ"
    assert result[RequisiteKind.DATE] == "14.01.2026"
    assert result[RequisiteKind.REGISTRATION_NUMBER] == "№ 7-ОД"
    assert result[RequisiteKind.PLACE] == "г. Москва"
    assert result[RequisiteKind.TITLE].startswith("Об утверждении")
    assert result[RequisiteKind.SIGNATURE] == "А.С. Ковалёва"


def test_spans_point_into_block_text() -> None:
    found = RequisiteDetector().detect(blocks("Москва, «03» февраля 2026 г."))
    [date] = [r for r in found if r.kind is RequisiteKind.DATE]
    assert "Москва, «03» февраля 2026 г."[date.start : date.end] == date.value


def test_words_inside_sentences_are_not_stamps() -> None:
    found = RequisiteDetector().detect(blocks("Соблюдать конфиденциальность сведений."))
    assert RequisiteKind.ACCESS_RESTRICTION not in kinds(found)


def test_body_text_after_numbered_sections_is_not_a_header() -> None:
    blocks = [
        Block(ordinal=0, kind=BlockKind.HEADING, text="ПОЛОЖЕНИЕ"),
        Block(ordinal=1, kind=BlockKind.HEADING, text="Общие положения", label="1."),
        Block(
            ordinal=2,
            kind=BlockKind.LIST_ITEM,
            text="Положение действует в ООО «Полярная звезда».",
            label="1.1.",
        ),
    ]
    assert RequisiteKind.ORGANIZATION_NAME not in kinds(RequisiteDetector().detect(blocks))


def test_a_date_in_any_spelling_is_the_date_requisite() -> None:
    # The spelling is judged by the date format check, not by the detector.
    for text, value in (
        ("Редакция от 1.2.2026", "1.2.2026"),
        ("2026-02-03", "2026-02-03"),
        ("«5» июня 2026 г.", "«5» июня 2026 г."),
    ):
        assert kinds(RequisiteDetector().detect(blocks(text)))[RequisiteKind.DATE] == value


def test_a_standard_number_is_not_a_date() -> None:
    found = RequisiteDetector().detect(blocks("По ГОСТ Р 7.0.97-2016 и пункту 1.12.2026.1"))
    assert RequisiteKind.DATE not in kinds(found)


def test_the_date_and_number_of_a_cited_act_are_not_the_documents() -> None:
    found = kinds(
        RequisiteDetector().detect(
            blocks(
                "ПРИКАЗ",
                "Во исполнение Федерального закона от 27.07.2006 № 152-ФЗ ПРИКАЗЫВАЮ:",
            )
        )
    )
    assert RequisiteKind.DATE not in found
    assert RequisiteKind.REGISTRATION_NUMBER not in found


def test_an_approval_by_order_carries_the_documents_date() -> None:
    found = kinds(
        RequisiteDetector().detect(
            blocks("УТВЕРЖДЕНА", "приказом генерального директора от 12.01.2026 № 3-ОД")
        )
    )
    assert found[RequisiteKind.DATE] == "12.01.2026"
    assert found[RequisiteKind.REGISTRATION_NUMBER] == "№ 3-ОД"
