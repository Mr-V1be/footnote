from __future__ import annotations

from collections.abc import Sequence

from snoska.domain.documents.requisites import RequisiteDetector
from snoska.domain.documents.structure import Block, BlockKind, Requisite, RequisiteKind


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
