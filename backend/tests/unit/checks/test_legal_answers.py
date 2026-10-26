"""Verdicts of a batch are accepted one by one, only when well-formed and grounded."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from footnote.application.checks.legal.answer import parse_batch
from footnote.application.checks.legal.executor import outcome_of
from footnote.application.checks.legal.index import Fragment
from footnote.application.checks.legal.prompt import PreparedCheck, build_batch_context
from footnote.application.checks.norms import Provision
from footnote.domain.checks.catalog import (
    CheckDefinition,
    CheckMethod,
    LawNorm,
    ModelBrief,
    Severity,
)
from footnote.domain.checks.outcome import FindingKind, ResultStatus
from footnote.domain.documents.structure import Block, BlockKind
from footnote.domain.shared.locale import Locale, LocalizedText

PURPOSES = "Оператор обрабатывает персональные данные в целях исполнения трудовых договоров."
TERMS = "Персональные данные хранятся не дольше, чем этого требуют цели обработки."
BLOCKS = {
    4: Block(4, BlockKind.PARAGRAPH, PURPOSES),
    9: Block(9, BlockKind.PARAGRAPH, TERMS),
}
PURPOSES_LAW = Provision(
    uuid4(), "152-fz", "st-18.1/ch-1/p-2", LocalizedText.source("п. 2 ч. 1 ст. 18.1 152-ФЗ"), "…"
)
TERMS_LAW = Provision(
    uuid4(), "152-fz", "st-5/ch-7", LocalizedText.source("ч. 7 ст. 5 152-ФЗ"), "…"
)
TEXT = LocalizedText({Locale.RU: "…", Locale.EN: "…"})


def prepared(code: str, law: Provision, fragments: list[Fragment]) -> PreparedCheck:
    brief = ModelBrief(question=f"Требование {code}", criteria="…", search=code)
    check = CheckDefinition(
        code=code,
        family="personal_data",
        method=CheckMethod.MODEL,
        severity=Severity.IMPORTANT,
        kinds=frozenset({"pd_policy"}),
        title=TEXT,
        requirement=TEXT,
        recommendation=TEXT,
        norm=LawNorm(act_code="152-fz", anchors=(law.anchor,)),
        brief=brief,
    )
    return PreparedCheck(check, brief, (law,), tuple(fragments))


CONTEXT = build_batch_context(
    [
        prepared("purposes", PURPOSES_LAW, [Fragment(4, "Цели", "3.1.", PURPOSES)]),
        prepared("terms", TERMS_LAW, [Fragment(9, "Сроки", "6.2.", TERMS)]),
    ]
)


def verdict(
    check: str,
    value: str,
    quotes: list[dict[str, str]],
    norm: str = "N1",
    explanation: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "check": check,
        "verdict": value,
        "quotes": quotes,
        "norm": norm,
        "explanation": explanation or {"ru": "Пояснение.", "en": "An explanation."},
        "recommendation": {"ru": "", "en": ""},
    }


def batch(*verdicts: dict[str, object]) -> str:
    return json.dumps({"verdicts": list(verdicts)}, ensure_ascii=False)


def test_requirements_share_passages_but_keep_their_own_provisions() -> None:
    assert list(CONTEXT.fragments) == ["D1", "D2"]
    assert CONTEXT.norms_of == {"C1": ("N1",), "C2": ("N2",)}


def test_a_grounded_verdict_locates_its_quote_and_a_bad_one_is_kept_apart() -> None:
    parsed = parse_batch(
        batch(
            verdict("C1", "present", [{"fragment": "D1", "text": "в целях исполнения трудовых"}]),
            verdict("C2", "present", [{"fragment": "D2", "text": "хранятся вечно"}], norm="N2"),
        ),
        CONTEXT,
        BLOCKS,
    )
    [location] = parsed.answers["C1"].quotes
    assert PURPOSES[location.start : location.end] == "в целях исполнения трудовых"
    assert "C2" in parsed.problems
    assert "C2" not in parsed.answers
    passed = outcome_of(parsed.answers["C1"], CONTEXT.context_of("C1"), attempts=1)
    assert passed.status is ResultStatus.PASSED


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("не JSON", "JSON"),
        (batch(verdict("C1", "maybe", [])), "verdict"),
        (
            batch(verdict("C1", "present", [{"fragment": "D1", "text": "в целях"}], norm="N2")),
            "норма",
        ),
        (batch(verdict("C1", "present", [])), "цитата"),
        (batch(), "нет вердикта"),
        (batch(verdict("C1", "absent", [], explanation={"ru": "Нет целей.", "en": ""})), "en"),
        (batch(verdict("C1", "absent", [], norm="N1, N2")), "одна норма"),
    ],
    ids=[
        "not json",
        "unknown verdict",
        "another requirement's norm",
        "no quote",
        "missing",
        "explained in one language only",
        "a list of norms",
    ],
)
def test_ungrounded_or_malformed_verdicts_are_refused(text: str, problem: str) -> None:
    parsed = parse_batch(text, CONTEXT, BLOCKS)
    assert "C1" not in parsed.answers
    assert problem in parsed.problems["C1"]


def test_verdicts_map_to_findings_honestly() -> None:
    parsed = parse_batch(
        batch(verdict("C1", "absent", []), verdict("C2", "uncertain", [], norm="N2")),
        CONTEXT,
        BLOCKS,
    )
    missing = outcome_of(parsed.answers["C1"], CONTEXT.context_of("C1"), attempts=1)
    review = outcome_of(parsed.answers["C2"], CONTEXT.context_of("C2"), attempts=2)
    assert missing.status is ResultStatus.VIOLATION
    assert missing.findings[0].location is None, "absence concerns the whole document"
    explained = missing.findings[0].detail.text
    assert explained is not None
    assert explained.resolve(Locale.EN) == "An explanation."
    assert explained.resolve(Locale.RU) == "Пояснение."
    assert review.status is ResultStatus.NEEDS_REVIEW
    assert review.findings[0].kind is FindingKind.REVIEW
    assert review.cited is not None
    assert review.cited.anchor == "st-5/ch-7"
