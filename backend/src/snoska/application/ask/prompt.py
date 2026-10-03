from __future__ import annotations

from collections.abc import Mapping, Sequence

from snoska.domain.ask.answer import SourceProvision, Turn
from snoska.ports.ai import ChatMessage, MessageRole

SYSTEM_PROMPT = "\n".join(
    (
        "Ты отвечаешь на вопросы о нормах права, опираясь только на приведённые положения.",
        "Каждое утверждение ответа подкрепи сноской [1], [2]… прямо в тексте ответа и для "
        "каждой сноски дай ключ положения (N1, N2…) и дословную цитату из него — слова, "
        "на которых держится утверждение.",
        "Цитата — короткий отрывок, не длиннее 30 слов; пропущенные слова обозначай «…».",
        "Не добавляй сведений, которых нет в положениях, и не давай советов сверх них.",
        "Если в положениях нет ответа на вопрос, верни found = false: честно сказать "
        "«в норме не найдено» лучше, чем ответить без опоры.",
        "Пиши по-русски, коротко и ясно, без вступлений.",
    )
)

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
    question: str, sources: Sequence[SourceProvision], earlier: Sequence[Turn]
) -> tuple[ChatMessage, ...]:
    provisions = "\n\n".join(
        f"{source.key} ({source.citation}):\n{source.text}" for source in sources
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
        ChatMessage(MessageRole.SYSTEM, SYSTEM_PROMPT),
        ChatMessage(MessageRole.USER, "\n\n".join(parts)),
    )


def correction(problem: str) -> ChatMessage:
    return ChatMessage(
        MessageRole.USER,
        f"Ответ не принят: {problem} Исправь и верни ответ по той же схеме.",
    )
