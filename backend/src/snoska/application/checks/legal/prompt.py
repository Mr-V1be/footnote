from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from snoska.application.checks.legal.index import Fragment
from snoska.application.checks.norms import Provision
from snoska.domain.checks.catalog import ModelBrief
from snoska.ports.ai import ChatMessage, MessageRole

VERDICTS = ("present", "partial", "absent", "uncertain")
MAX_QUOTES = 2

# The language of the instructions is the language of the documents: the
# model reads Russian law and Russian documents and answers in Russian.
ANSWER_EXAMPLE = {
    "verdict": "present | partial | absent | uncertain",
    "quotes": [{"fragment": "D1", "text": "дословная цитата"}],
    "norm": "N1",
    "explanation": "одно предложение",
    "recommendation": "одно предложение, как исправить",
}

SYSTEM_PROMPT = "\n".join(
    [
        "Ты юрист по персональным данным и проверяешь документ на соответствие 152-ФЗ.",
        "Тебе дают одно требование, нормы закона [N…] и фрагменты проверяемого документа [D…].",
        "Реши, выполнено ли требование в документе.",
        "",
        "Правила:",
        "- опирайся только на данные фрагменты и нормы, ничего не додумывай;",
        "- цитаты — короткие дословные отрывки из текста фрагментов D, не длиннее 15 слов;",
        "- норму указывай только из списка N — ту, на которой основан вывод.",
        "",
        "verdict:",
        "- present — требование выполнено; приведи цитату, которая это подтверждает;",
        "- partial — выполнено не полностью; процитируй, что есть, и объясни, чего не хватает;",
        "- absent — во фрагментах этого нет;",
        "- uncertain — по фрагментам нельзя уверенно судить.",
        "",
        "Ответь одним JSON-объектом без пояснений вокруг:",
        json.dumps(ANSWER_EXAMPLE, ensure_ascii=False),
        "Для present и uncertain recommendation — пустая строка.",
    ]
)

ANSWER_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "quotes": {
            "type": "array",
            "maxItems": MAX_QUOTES,
            "items": {
                "type": "object",
                "properties": {
                    "fragment": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["fragment", "text"],
            },
        },
        "norm": {"type": "string"},
        "explanation": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    "required": ["verdict", "quotes", "norm", "explanation", "recommendation"],
}


@dataclass(frozen=True, slots=True)
class Context:
    """What the model is shown, with the ids it refers to."""

    norms: Mapping[str, Provision]
    fragments: Mapping[str, Fragment]


def build_context(provisions: Sequence[Provision], fragments: Sequence[Fragment]) -> Context:
    return Context(
        norms={f"N{index}": provision for index, provision in enumerate(provisions, start=1)},
        fragments={f"D{index}": fragment for index, fragment in enumerate(fragments, start=1)},
    )


def _fragment_line(key: str, fragment: Fragment) -> str:
    place = [f"раздел «{fragment.section}»" if fragment.section else None]
    place.append(f"п. {fragment.label}" if fragment.label else None)
    where = ", ".join(part for part in place if part)
    return f"[{key}] ({where}) {fragment.text}" if where else f"[{key}] {fragment.text}"


def build_messages(
    brief: ModelBrief, context: Context, document_title: str, outline: Sequence[str]
) -> tuple[ChatMessage, ...]:
    norms = "\n".join(
        f"[{key}] {provision.citation}: {provision.text}"
        for key, provision in context.norms.items()
    )
    fragments = "\n".join(_fragment_line(key, item) for key, item in context.fragments.items())
    contents = " / ".join(outline) if outline else "—"
    user = (
        f"Требование: {brief.question}\n"
        f"Считается выполненным, если: {brief.criteria}\n\n"
        f"Нормы:\n{norms}\n\n"
        f"Документ «{document_title}». Разделы: {contents}\n"
        f"Фрагменты:\n{fragments}"
    )
    return (
        ChatMessage(MessageRole.SYSTEM, SYSTEM_PROMPT),
        ChatMessage(MessageRole.USER, user),
    )


def correction(problem: str) -> ChatMessage:
    """Asks the model to fix an answer that could not be accepted."""
    return ChatMessage(
        MessageRole.USER,
        f"Ответ не принят: {problem} Исправь и пришли JSON-объект целиком заново.",
    )
