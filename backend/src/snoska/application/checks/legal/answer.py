from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from snoska.application.checks.legal.prompt import MAX_QUOTES, VERDICTS, BatchContext, Context
from snoska.domain.checks.grounding import locate_quote
from snoska.domain.checks.outcome import TextLocation
from snoska.domain.documents.structure import Block
from snoska.domain.shared.text import normalize_whitespace

MAX_TEXT_CHARS = 700
GROUNDED_VERDICTS = frozenset({"present", "partial"})


class InvalidAnswer(Exception):  # noqa: N818 - the name reads as the verdict on an answer
    """The model's answer cannot be accepted. ``problem`` is told back to the model."""

    def __init__(self, problem: str) -> None:
        super().__init__(problem)
        self.problem = problem


@dataclass(frozen=True, slots=True)
class Answer:
    """A model answer that passed every check of form and grounding."""

    verdict: str
    quotes: tuple[TextLocation, ...]
    norm_key: str
    explanation: str
    recommendation: str


def _text(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise InvalidAnswer(f"поле {key} должно быть строкой.")
    return normalize_whitespace(value)[:MAX_TEXT_CHARS]


def _quotes(
    data: Mapping[str, object], context: Context, blocks: Mapping[int, Block]
) -> tuple[TextLocation, ...]:
    raw = data.get("quotes")
    if not isinstance(raw, list):
        raise InvalidAnswer("поле quotes должно быть списком.")
    located: list[TextLocation] = []
    for item in raw[:MAX_QUOTES]:
        if not isinstance(item, dict):
            raise InvalidAnswer("каждая цитата — объект с полями fragment и text.")
        key, quote = item.get("fragment"), item.get("text")
        if not isinstance(quote, str):
            raise InvalidAnswer("текст цитаты должен быть строкой.")
        location = _locate(context, blocks, key, quote)
        if location is None:
            raise InvalidAnswer(
                f"цитата «{quote[:80]}» не найдена дословно ни в одном фрагменте; "
                "цитируй непрерывный отрывок одного фрагмента."
            )
        located.append(location)
    return tuple(located)


def _locate(
    context: Context, blocks: Mapping[int, Block], key: object, quote: str
) -> TextLocation | None:
    """Where a quote is in the document: in the fragment it names, or else in
    another fragment the model was shown. Either way it is verbatim text of
    the document, which is all grounding requires."""
    named = context.fragments.get(key) if isinstance(key, str) else None
    candidates = [named] if named is not None else []
    candidates += [fragment for fragment in context.fragments.values() if fragment is not named]
    for fragment in candidates:
        span = locate_quote(blocks[fragment.block_ordinal].text, quote)
        if span is not None:
            return TextLocation(fragment.block_ordinal, *span)
    return None


def parse_verdict(
    data: Mapping[str, object], context: Context, blocks: Mapping[int, Block]
) -> Answer:
    """Accept a verdict only if it is well-formed and grounded.

    Grounded means: every quote is found word for word in a passage the
    model was shown, and the norm is one of those given for the requirement.
    A verdict that the requirement is met, fully or in part, must be backed
    by a quote.
    """
    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        raise InvalidAnswer(f"verdict должен быть одним из: {', '.join(VERDICTS)}.")
    norm = data.get("norm")
    if not isinstance(norm, str) or norm not in context.norms:
        raise InvalidAnswer(f"норма {norm!r} не из списка требования: {', '.join(context.norms)}.")
    quotes = _quotes(data, context, blocks)
    if verdict in GROUNDED_VERDICTS and not quotes:
        raise InvalidAnswer("для present и partial нужна хотя бы одна дословная цитата.")
    explanation = _text(data, "explanation")
    if not explanation:
        raise InvalidAnswer("поле explanation не заполнено.")
    return Answer(
        verdict=str(verdict),
        quotes=quotes,
        norm_key=norm,
        explanation=explanation,
        recommendation=_text(data, "recommendation"),
    )


@dataclass(frozen=True, slots=True)
class BatchAnswers:
    """The verdicts accepted, and for the rest what was wrong (by key)."""

    answers: Mapping[str, Answer]
    problems: Mapping[str, str]


def parse_batch(text: str, context: BatchContext, blocks: Mapping[int, Block]) -> BatchAnswers:
    """Each verdict of a batch is judged on its own: one bad verdict does not
    reject the others, and only the rejected ones are asked again."""
    keys = list(context.checks)
    try:
        data = json.loads(text)
    except ValueError:
        return BatchAnswers({}, dict.fromkeys(keys, "ответ не является корректным JSON."))
    items = data.get("verdicts") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return BatchAnswers({}, dict.fromkeys(keys, "нужен объект с массивом verdicts."))
    answers: dict[str, Answer] = {}
    problems: dict[str, str] = {}
    for item in items:
        key = item.get("check") if isinstance(item, dict) else None
        if not isinstance(key, str) or key not in context.checks or key in answers:
            continue
        try:
            answers[key] = parse_verdict(item, context.context_of(key), blocks)
            problems.pop(key, None)
        except InvalidAnswer as exc:
            problems[key] = exc.problem
    for key in keys:
        if key not in answers and key not in problems:
            problems[key] = "нет вердикта по этому требованию."
    return BatchAnswers(answers, problems)
