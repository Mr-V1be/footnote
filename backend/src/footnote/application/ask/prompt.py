from __future__ import annotations

from collections.abc import Mapping, Sequence

from footnote.application.shared.languages import LANGUAGE_NAMES
from footnote.domain.ask.answer import SourceProvision, Turn
from footnote.domain.shared.locale import SOURCE_LOCALE, Locale
from footnote.ports.ai import ChatMessage, MessageRole

_RULES = (
    "Ты отвечаешь на вопросы о нормах права, опираясь только на приведённые положения.",
    "Каждое утверждение ответа подкрепи сноской [1], [2]… прямо в тексте ответа и для "
    "каждой сноски дай ключ положения (N1, N2…) и дословную цитату из него — слова, "
    "на которых держится утверждение.",
    "Цитата — короткий отрывок, не длиннее 30 слов; пропущенные слова обозначай «…».",
    "Не добавляй сведений, которых нет в положениях, и не давай советов сверх них.",
    "Если в положениях нет ответа на вопрос, верни found = false: честно сказать "
    "«в норме не найдено» лучше, чем ответить без опоры.",
)


def system_prompt(locale: Locale) -> str:
    """The instructions, with the answer in the asker's language. Quotes stay
    in the language of the law: they are its words, found in it verbatim."""
    language = LANGUAGE_NAMES[locale]
    if locale is SOURCE_LOCALE:
        closing = f"Пиши {language}, коротко и ясно, без вступлений."
    else:
        closing = (
            f"Текст ответа (answer) пиши {language}, коротко и ясно, без вступлений; "
            "цитаты (quote) не переводи — они дословно из положений."
        )
    return "\n".join((*_RULES, closing))


ANSWER_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"norm": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["norm", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["found", "answer", "citations"],
    "additionalProperties": False,
}

# Earlier turns given to the model, so a follow-up question reads in context.
CONTEXT_TURNS = 2


def build_messages(
    question: str, sources: Sequence[SourceProvision], earlier: Sequence[Turn], locale: Locale
) -> tuple[ChatMessage, ...]:
    provisions = "\n\n".join(
        f"{source.key} ({source.citation.resolve(SOURCE_LOCALE)}):\n{source.text}"
        for source in sources
    )
    context = "\n".join(
        f"Вопрос: {turn.question}\nОтвет: {turn.answer.text or 'в норме не найдено'}"
        for turn in earlier[-CONTEXT_TURNS:]
    )
    parts = [f"Вопрос: {question}"]
    if context:
        parts.append(f"Предыдущие вопросы этого разговора:\n{context}")
    parts.append(f"Положения:\n\n{provisions}")
    return (
        ChatMessage(MessageRole.SYSTEM, system_prompt(locale)),
        ChatMessage(MessageRole.USER, "\n\n".join(parts)),
    )


def correction(problem: str) -> ChatMessage:
    return ChatMessage(
        MessageRole.USER,
        f"Ответ не принят: {problem} Исправь и верни ответ по той же схеме.",
    )
