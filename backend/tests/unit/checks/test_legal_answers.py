"""A model answer is accepted only when it is well-formed and grounded."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from snoska.application.checks.legal.answer import InvalidAnswer, parse_answer
from snoska.application.checks.legal.executor import outcome_of
from snoska.application.checks.legal.index import Fragment
from snoska.application.checks.legal.prompt import build_context
from snoska.application.checks.norms import Provision
from snoska.domain.checks.outcome import FindingKind, ResultStatus
from snoska.domain.documents.structure import Block, BlockKind

PURPOSES = "Оператор обрабатывает персональные данные в целях исполнения трудовых договоров."
TERMS = "Персональные данные хранятся не дольше, чем этого требуют цели обработки."
BLOCKS = {
    4: Block(4, BlockKind.PARAGRAPH, PURPOSES),
    9: Block(9, BlockKind.PARAGRAPH, TERMS),
}
CONTEXT = build_context(
    [Provision(uuid4(), "152-fz", "st-18.1/ch-1/p-2", "п. 2 ч. 1 ст. 18.1 152-ФЗ", "…")],
    [Fragment(4, "Цели", "3.1.", PURPOSES), Fragment(9, "Сроки", "6.2.", TERMS)],
)


def answer(verdict: str, quotes: list[dict[str, str]], norm: str = "N1") -> str:
    return json.dumps(
        {
            "verdict": verdict,
            "quotes": quotes,
            "norm": norm,
            "explanation": "Цели названы.",
            "recommendation": "",
        },
        ensure_ascii=False,
    )


def test_a_grounded_answer_locates_its_quote_in_the_document() -> None:
    parsed = parse_answer(
        answer("present", [{"fragment": "D1", "text": "в целях исполнения трудовых договоров"}]),
        CONTEXT,
        BLOCKS,
    )
    [location] = parsed.quotes
    assert location.block_ordinal == 4
    assert PURPOSES[location.start : location.end] == "в целях исполнения трудовых договоров"
    assert outcome_of(parsed, CONTEXT, attempts=1).status is ResultStatus.PASSED


def test_a_quote_attributed_to_the_wrong_passage_is_still_found_in_the_document() -> None:
    parsed = parse_answer(
        answer("partial", [{"fragment": "D1", "text": "хранятся не дольше, чем этого требуют"}]),
        CONTEXT,
        BLOCKS,
    )
    assert parsed.quotes[0].block_ordinal == 9


@pytest.mark.parametrize(
    "text",
    [
        "не JSON",
        answer("maybe", []),
        answer("present", [{"fragment": "D1", "text": "в целях исполнения"}], norm="N7"),
        answer("present", []),
        answer("partial", [{"fragment": "D2", "text": "Оператор хранит данные клиентов вечно"}]),
    ],
    ids=["not json", "unknown verdict", "norm not given", "no quote", "invented quote"],
)
def test_ungrounded_or_malformed_answers_are_refused(text: str) -> None:
    with pytest.raises(InvalidAnswer):
        parse_answer(text, CONTEXT, BLOCKS)


def test_verdicts_map_to_findings_honestly() -> None:
    absent = parse_answer(answer("absent", []), CONTEXT, BLOCKS)
    uncertain = parse_answer(answer("uncertain", []), CONTEXT, BLOCKS)
    missing = outcome_of(absent, CONTEXT, attempts=1)
    review = outcome_of(uncertain, CONTEXT, attempts=2)
    assert missing.status is ResultStatus.VIOLATION
    assert missing.findings[0].location is None, "absence concerns the whole document"
    assert review.status is ResultStatus.NEEDS_REVIEW
    assert review.findings[0].kind is FindingKind.REVIEW
    assert review.cited is not None
    assert review.cited.anchor == "st-18.1/ch-1/p-2"
