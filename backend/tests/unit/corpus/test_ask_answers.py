"""Answers to questions are accepted only when they hold to the provisions."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from snoska.domain.ask.answer import (
    AnswerStatus,
    SourceProvision,
    UngroundedAnswerError,
    read_answer,
    title_of,
)

SOURCE = SourceProvision(
    key="N1",
    act_code="152-fz",
    edition_id=uuid4(),
    anchor="st-9/ch-1",
    citation="ч. 1 ст. 9 152-ФЗ",
    text="Субъект персональных данных принимает решение о предоставлении его данных.",
)


def answer(**fields: object) -> str:
    return json.dumps({"found": True, "answer": "Да [1].", **fields}, ensure_ascii=False)


def test_a_grounded_answer_keeps_its_footnotes() -> None:
    read = read_answer(
        answer(
            citations=[{"norm": "N1", "quote": "субъект персональных данных принимает решение"}]
        ),
        [SOURCE],
    )
    assert read.status is AnswerStatus.ANSWERED
    [citation] = read.citations
    assert (citation.number, citation.citation) == (1, "ч. 1 ст. 9 152-ФЗ")
    assert citation.quote == "Субъект персональных данных принимает решение"


@pytest.mark.parametrize(
    "raw",
    [
        answer(citations=[{"norm": "N7", "quote": "принимает решение"}]),
        answer(citations=[{"norm": "N1", "quote": "оператор вправе всё"}]),
        json.dumps(
            {
                "found": True,
                "answer": "Без сносок.",
                "citations": [{"norm": "N1", "quote": "принимает решение"}],
            }
        ),
        "не json",
    ],
)
def test_an_ungrounded_answer_is_refused(raw: str) -> None:
    with pytest.raises(UngroundedAnswerError):
        read_answer(raw, [SOURCE])


def test_the_norm_may_be_silent() -> None:
    silent = read_answer(json.dumps({"found": False, "answer": "", "citations": []}), [SOURCE])
    assert (silent.status, silent.text, silent.citations) == (AnswerStatus.NOT_FOUND, None, ())


def test_titles_are_short() -> None:
    assert title_of("  Нужно   ли согласие? ") == "Нужно ли согласие?"
    assert len(title_of("слово " * 40)) == 80
