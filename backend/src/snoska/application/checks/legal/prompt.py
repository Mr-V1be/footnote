from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from snoska.application.checks.legal.index import Fragment
from snoska.application.checks.norms import Provision
from snoska.domain.checks.catalog import CheckDefinition, ModelBrief
from snoska.ports.ai import ChatMessage, MessageRole

VERDICTS = ("present", "partial", "absent", "uncertain")
MAX_QUOTES = 2
# The prompt's wording is part of every cached answer's key: change it and
# the answers are asked again.
PROMPT_VERSION = "batch-3"
# An answer takes about this many tokens per requirement; the reserve covers
# the wrapper and a model's reasoning, which counts against the same limit.
TOKENS_PER_VERDICT = 300
TOKENS_RESERVE = 1500
MAX_ANSWER_TOKENS = 12000

# The language of the instructions is the language of the documents: the
# model reads Russian law and Russian documents and answers in Russian.
VERDICT_EXAMPLE = {
    "check": "C1",
    "verdict": "present | partial | absent | uncertain",
    "quotes": [{"fragment": "D1", "text": "дословная цитата"}],
    "norm": "N1",
    "explanation": "одно предложение",
    "recommendation": "одно предложение, как исправить",
}

SYSTEM_PROMPT = "\n".join(
    [
        "Ты юрист по персональным данным и проверяешь документ на соответствие 152-ФЗ.",
        "Тебе дают несколько требований [C…], нормы закона [N…] и фрагменты "
        "проверяемого документа [D…].",
        "Для каждого требования реши, выполнено ли оно в документе.",
        "",
        "Правила:",
        "- опирайся только на данные фрагменты и нормы, ничего не додумывай;",
        "- цитаты — короткие дословные отрывки из текста фрагментов D, не длиннее 15 слов;",
        "- норму указывай только из тех, что перечислены у требования.",
        "",
        "verdict:",
        "- present — требование выполнено; приведи цитату, которая это подтверждает;",
        "- partial — выполнено не полностью; процитируй, что есть, и объясни, чего не хватает;",
        "- absent — во фрагментах этого нет;",
        "- uncertain — по фрагментам нельзя уверенно судить.",
        "",
        "Ответь одним JSON-объектом без пояснений вокруг: "
        '{"verdicts": [...]} — ровно по одному элементу на каждое требование, вида',
        json.dumps(VERDICT_EXAMPLE, ensure_ascii=False),
        "Для present и uncertain recommendation — пустая строка.",
        f"Версия инструкции: {PROMPT_VERSION}.",
    ]
)

_QUOTE_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"fragment": {"type": "string"}, "text": {"type": "string"}},
    "required": ["fragment", "text"],
    "additionalProperties": False,
}
VERDICT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "check": {"type": "string"},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "quotes": {"type": "array", "maxItems": MAX_QUOTES, "items": _QUOTE_SCHEMA},
        "norm": {"type": "string"},
        "explanation": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    "required": ["check", "verdict", "quotes", "norm", "explanation", "recommendation"],
    "additionalProperties": False,
}
BATCH_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"verdicts": {"type": "array", "items": VERDICT_SCHEMA}},
    "required": ["verdicts"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class PreparedCheck:
    """One requirement with what was found for it: the provisions it rests on
    and the passages of the document retrieved for it."""

    check: CheckDefinition
    brief: ModelBrief
    provisions: tuple[Provision, ...]
    fragments: tuple[Fragment, ...]


@dataclass(frozen=True, slots=True)
class Context:
    """What the model is shown for one requirement, with the ids it refers to."""

    norms: Mapping[str, Provision]
    fragments: Mapping[str, Fragment]


@dataclass(frozen=True, slots=True)
class BatchContext:
    """Several requirements in one request: shared numbering of provisions
    and passages, and for each requirement the provisions it may cite."""

    checks: Mapping[str, PreparedCheck]
    norms: Mapping[str, Provision]
    fragments: Mapping[str, Fragment]
    norms_of: Mapping[str, tuple[str, ...]]

    def context_of(self, key: str) -> Context:
        """The view of one requirement: its own provisions, every passage."""
        return Context(
            norms={norm: self.norms[norm] for norm in self.norms_of[key]},
            fragments=self.fragments,
        )


def build_batch_context(prepared: Sequence[PreparedCheck]) -> BatchContext:
    norms: dict[str, Provision] = {}
    norm_keys: dict[tuple[str, str], str] = {}
    fragments: dict[str, Fragment] = {}
    fragment_keys: dict[int, str] = {}
    checks: dict[str, PreparedCheck] = {}
    norms_of: dict[str, tuple[str, ...]] = {}
    for index, item in enumerate(prepared, start=1):
        key = f"C{index}"
        checks[key] = item
        own: list[str] = []
        for provision in item.provisions:
            identity = (provision.act_code, provision.anchor)
            if identity not in norm_keys:
                norm_keys[identity] = f"N{len(norm_keys) + 1}"
                norms[norm_keys[identity]] = provision
            if norm_keys[identity] not in own:
                own.append(norm_keys[identity])
        norms_of[key] = tuple(own)
        for fragment in item.fragments:
            if fragment.block_ordinal not in fragment_keys:
                fragment_keys[fragment.block_ordinal] = f"D{len(fragment_keys) + 1}"
                fragments[fragment_keys[fragment.block_ordinal]] = fragment
    ordered = dict(sorted(fragments.items(), key=lambda item: item[1].block_ordinal))
    return BatchContext(checks=checks, norms=norms, fragments=ordered, norms_of=norms_of)


def _fragment_line(key: str, fragment: Fragment) -> str:
    place = [f"раздел «{fragment.section}»" if fragment.section else None]
    place.append(f"п. {fragment.label}" if fragment.label else None)
    where = ", ".join(part for part in place if part)
    return f"[{key}] ({where}) {fragment.text}" if where else f"[{key}] {fragment.text}"


def build_messages(
    context: BatchContext,
    outline: Sequence[str],
    problems: Mapping[str, str] | None = None,
) -> tuple[ChatMessage, ...]:
    """The request for the requirements of ``context``. ``problems`` are what
    was wrong with an earlier answer to the same requirements, by key.

    The request depends on the document's text only, not on the name it was
    uploaded under: the same text checked anywhere asks the same question,
    and its cached answer serves every copy."""
    requirements = "\n\n".join(
        f"[{key}] {item.brief.question}\n"
        f"Выполнено, если: {item.brief.criteria}\n"
        f"Нормы требования: {', '.join(context.norms_of[key])}"
        for key, item in context.checks.items()
    )
    norms = "\n".join(
        f"[{key}] {provision.citation}: {provision.text}"
        for key, provision in context.norms.items()
    )
    fragments = "\n".join(_fragment_line(key, item) for key, item in context.fragments.items())
    contents = " / ".join(outline) if outline else "—"
    parts = [
        f"Требования:\n{requirements}",
        f"Нормы:\n{norms}",
        f"Разделы документа: {contents}\nФрагменты:\n{fragments}",
    ]
    if problems:
        notes = "\n".join(f"- {key}: {problem}" for key, problem in problems.items())
        parts.append(f"Прошлый ответ не принят:\n{notes}\nОтветь на эти требования заново.")
    return (
        ChatMessage(MessageRole.SYSTEM, SYSTEM_PROMPT),
        ChatMessage(MessageRole.USER, "\n\n".join(parts)),
    )


def answer_tokens(checks: int) -> int:
    return min(TOKENS_RESERVE + TOKENS_PER_VERDICT * checks, MAX_ANSWER_TOKENS)
