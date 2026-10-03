from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from snoska.domain.checks.grounding import locate_quote

QUESTION_MAX_LENGTH = 1_000
TITLE_LENGTH = 80
_MARKER = re.compile(r"\[(\d{1,2})\]")


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    # The provisions found do not answer the question: said plainly.
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class SourceProvision:
    """A provision shown to the model, under the key it is cited by (N1...)."""

    key: str
    act_code: str
    edition_id: UUID
    anchor: str
    citation: str
    text: str


@dataclass(frozen=True, slots=True)
class Citation:
    """A footnote of an answer: the number in the text, the provision, and
    the words of the provision the answer rests on."""

    number: int
    act_code: str
    edition_id: UUID
    anchor: str
    citation: str
    quote: str


@dataclass(frozen=True, slots=True)
class Answer:
    status: AnswerStatus
    text: str | None
    citations: tuple[Citation, ...]


class UngroundedAnswerError(ValueError):
    """The model's answer does not hold to the provisions it was given."""

    def __init__(self, problem: str) -> None:
        super().__init__(problem)
        self.problem = problem


def read_answer(raw: str, sources: Sequence[SourceProvision]) -> Answer:
    """Accept an answer only if every citation names a given provision and
    quotes it word for word, and every footnote in the text has a citation."""
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UngroundedAnswerError("ответ не JSON.") from exc
    if not isinstance(data, dict):
        raise UngroundedAnswerError("ответ должен быть JSON-объектом.")
    if not data.get("found"):
        return Answer(status=AnswerStatus.NOT_FOUND, text=None, citations=())
    by_key: Mapping[str, SourceProvision] = {source.key: source for source in sources}
    text = str(data.get("answer") or "").strip()
    items = data.get("citations") or []
    if not text or not isinstance(items, list) or not items:
        raise UngroundedAnswerError("ответ без текста или без ссылок на положения.")
    citations: list[Citation] = []
    for number, item in enumerate(items, start=1):
        source = by_key.get(str(item.get("norm", "")) if isinstance(item, dict) else "")
        quote = str(item.get("quote", "")).strip() if isinstance(item, dict) else ""
        if source is None:
            raise UngroundedAnswerError(
                f"ссылка {number} указывает на положение, которого не было."
            )
        span = locate_quote(source.text, quote)
        if span is None:
            raise UngroundedAnswerError(
                f"цитата {number} не найдена дословно в положении {source.key}."
            )
        citations.append(
            Citation(
                number=number,
                act_code=source.act_code,
                edition_id=source.edition_id,
                anchor=source.anchor,
                citation=source.citation,
                quote=source.text[span[0] : span[1]],
            )
        )
    used = {int(found) for found in _MARKER.findall(text)}
    if not used or not used <= set(range(1, len(citations) + 1)):
        raise UngroundedAnswerError(
            "в тексте ответа должны стоять сноски [1], [2]… на приведённые ссылки."
        )
    return Answer(status=AnswerStatus.ANSWERED, text=text, citations=tuple(citations))


@dataclass(frozen=True, slots=True)
class Turn:
    """A question and its answer in a conversation."""

    id: UUID
    conversation_id: UUID
    ordinal: int
    question: str
    answer: Answer
    model: str
    asked_at: datetime


@dataclass(frozen=True, slots=True)
class Conversation:
    id: UUID
    organization_id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


def title_of(question: str) -> str:
    words = " ".join(question.split())
    return words if len(words) <= TITLE_LENGTH else words[: TITLE_LENGTH - 1].rstrip() + "…"
