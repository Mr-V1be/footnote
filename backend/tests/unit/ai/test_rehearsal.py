"""The rehearsal provider: rules, not a model, in the product's schemas."""

from __future__ import annotations

import json
import math

from snoska.application.ask.prompt import ANSWER_SCHEMA as QUESTION_SCHEMA
from snoska.application.checks.legal.prompt import ANSWER_SCHEMA as CHECK_SCHEMA
from snoska.infrastructure.ai.rehearsal import FeatureHashEmbedder, RehearsalLanguageModel
from snoska.ports.ai import ChatMessage, CompletionRequest, MessageRole

CHECK_PROMPT = (
    "Требование: В документе указаны цели обработки персональных данных\n"
    "Считается выполненным, если: перечислены конкретные цели обработки\n\n"
    "Нормы:\n[N1] ч. 2 ст. 5 152-ФЗ: Обработка ограничивается достижением целей.\n\n"
    "Документ «Политика». Разделы: —\n"
    "Фрагменты:\n"
    "[D1] Оператор обрабатывает персональные данные гостей в целях обработки заказов.\n"
    "[D2] Документ утверждён приказом директора."
)


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


async def test_texts_sharing_words_are_near_and_vectors_are_unit_length() -> None:
    embedder = FeatureHashEmbedder()
    consent, withdrawal, weather = await embedder.embed(
        [
            "Согласие на обработку персональных данных",
            "Отзыв согласия на обработку персональных данных",
            "Прогноз погоды на завтра",
        ]
    )
    assert math.isclose(sum(v * v for v in consent), 1.0, rel_tol=1e-9)
    assert cosine(consent, withdrawal) > cosine(consent, weather)


async def test_a_check_is_answered_by_quoting_the_closest_fragment_verbatim() -> None:
    request = CompletionRequest(
        messages=(ChatMessage(MessageRole.USER, CHECK_PROMPT),), response_schema=CHECK_SCHEMA
    )
    answer = json.loads((await RehearsalLanguageModel().complete(request)).text)
    assert answer["verdict"] in ("present", "partial")
    assert answer["quotes"][0]["fragment"] == "D1"
    assert answer["quotes"][0]["text"] in CHECK_PROMPT
    assert answer["norm"] == "N1"
    assert answer["explanation"].startswith("Черновик без модели")


async def test_a_question_without_shared_words_is_not_found() -> None:
    prompt = (
        "Вопрос: Какая завтра погода?\n\nПоложения:\n\n"
        "N1 (ч. 1 ст. 9 152-ФЗ):\nСубъект принимает решение о предоставлении своих данных."
    )
    request = CompletionRequest(
        messages=(ChatMessage(MessageRole.USER, prompt),), response_schema=QUESTION_SCHEMA
    )
    answer = json.loads((await RehearsalLanguageModel().complete(request)).text)
    assert answer == {"found": False, "answer": "", "citations": []}
