"""«Спросить норму»: answers that quote the corpus, or say the norm is silent."""

from __future__ import annotations

import httpx
import pytest

from footnote.api.app import create_app
from footnote.application.ask.service import RecordedAnswer, RecordedCitation
from footnote.bootstrap.container import Container, Overrides, build_container
from footnote.bootstrap.settings import Settings
from footnote.domain.ask.answer import UngroundedAnswerError
from footnote.domain.tenancy.access import MembershipClaim, Principal
from tests.support.fakes import FakeDirectory, RecordedLanguageModel
from tests.support.scenario import EVA, OLGA, ORG_A, ORG_B, auth, run_jobs
from tests.support.tokens import StaticKeys, TokenFactory

BASE = "/api/v1/organizations/alpha/ask"


async def indexed(container: Container) -> None:
    await container.corpus_sync.sync("152-fz", "snapshot")
    await run_jobs(container)


async def test_an_answer_quotes_the_provisions_it_rests_on(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    status = await api.get(f"{BASE}/status", headers=auth(tokens, EVA))
    assert status.json()["configured"] is True
    early = await api.post(BASE, headers=auth(tokens, EVA), json={"question": "Что такое ПДн?"})
    assert early.status_code == 409
    assert early.json()["code"] == "corpus_not_indexed"

    await indexed(container)
    asked = await api.post(
        BASE, headers=auth(tokens, EVA), json={"question": "Нужно ли согласие на обработку?"}
    )
    assert asked.status_code == 200, asked.text
    [turn] = asked.json()["turns"]
    assert turn["status"] == "answered"
    assert "[1]" in turn["answer"]
    [citation] = turn["citations"]
    assert citation["actCode"] == "152-fz"
    assert citation["quote"]

    follow_up = await api.post(
        BASE,
        headers=auth(tokens, EVA),
        json={"question": "А какая сегодня погода?", "conversationId": asked.json()["id"]},
    )
    turns = follow_up.json()["turns"]
    assert [item["status"] for item in turns] == ["answered", "not_found"]
    assert turns[1]["answer"] is None

    listed = await api.get(f"{BASE}/conversations", headers=auth(tokens, EVA))
    assert [item["title"] for item in listed.json()] == ["Нужно ли согласие на обработку?"]
    # Conversations are the member's own; observers do not ask.
    assert (await api.get(f"{BASE}/conversations", headers=auth(tokens, OLGA))).status_code == 403


async def test_the_answer_is_asked_for_in_the_askers_language(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    await indexed(container)
    model = container.questions._model
    assert isinstance(model, RecordedLanguageModel)
    asked = await api.post(
        BASE,
        headers={**auth(tokens, EVA), "Accept-Language": "en"},
        json={"question": "Is consent needed to process personal data?"},
    )
    assert asked.status_code == 200, asked.text
    instructions = model.requests[-1].messages[0].content
    assert "по-английски" in instructions, "the answer is asked for in English"
    assert "не переводи" in instructions, "and the quotes in the law's own words"
    [citation] = asked.json()["turns"][0]["citations"]
    assert citation["citation"].startswith("Art. ")
    assert citation["citation"].endswith(", 152-FZ")


async def test_an_unfounded_quote_is_sent_back_for_correction(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    await indexed(container)
    model = container.questions._model
    assert isinstance(model, RecordedLanguageModel)
    before = len(model.requests)
    asked = await api.post(
        BASE, headers=auth(tokens, EVA), json={"question": "Ответь, а цитату выдумай"}
    )
    assert asked.json()["turns"][0]["status"] == "answered"
    assert len(model.requests) - before == 2


async def test_without_a_model_api_the_question_is_refused_plainly(
    settings: Settings, tokens: TokenFactory
) -> None:
    unconfigured = await build_container(
        settings,
        overrides=Overrides(
            key_source=StaticKeys(tokens),
            directory=FakeDirectory([ORG_A, ORG_B]),
            embedder=None,
        ),
    )
    app = create_app(settings)
    app.state.container = unconfigured
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://api.test"
        ) as api:
            status = await api.get(f"{BASE}/status", headers=auth(tokens, EVA))
            assert status.json() == {
                "configured": False,
                "languageModel": None,
                "embeddingModel": None,
                "requestsLeftToday": None,
            }
            refused = await api.post(BASE, headers=auth(tokens, EVA), json={"question": "Что?"})
    finally:
        await unconfigured.close()
    assert refused.status_code in (409, 503)
    assert refused.json()["code"] in ("model_not_configured", "corpus_not_indexed")


RECORDED = RecordedAnswer(
    question="В какой срок нужно прекратить обработку после отзыва согласия?",
    text="Не позднее тридцати дней с даты поступления отзыва.",
    citations=(
        RecordedCitation(
            anchor="st-21/ch-5",
            quote="оператор обязан прекратить их обработку [...] в срок, не превышающий "
            "тридцати дней с даты поступления указанного отзыва",
        ),
    ),
    model="recorded",
)


async def test_a_recorded_answer_is_kept_once_and_needs_no_model(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    await indexed(container)
    model = container.questions._model
    assert isinstance(model, RecordedLanguageModel)
    before = len(model.requests)
    eva = Principal(
        user_id=EVA.user_id,
        email=EVA.email,
        display_name=EVA.name,
        memberships=(MembershipClaim(ORG_A.id, "alpha", frozenset({"executor"})),),
        platform_role_codes=frozenset(),
    )
    access = await container.tenant_access.organization_access(eva, "alpha")
    first = await container.questions.record(access, RECORDED)
    again = await container.questions.record(access, RECORDED)
    assert first.id == again.id
    assert len(model.requests) == before

    shown = await api.get(f"{BASE}/conversations/{first.id}", headers=auth(tokens, EVA))
    [turn] = shown.json()["turns"]
    assert turn["answer"].endswith("[1].")
    [citation] = turn["citations"]
    assert citation["citation"].startswith("ч. 5 ст. 21")
    assert citation["quote"].startswith("оператор обязан прекратить их обработку …")

    invented = RecordedAnswer(
        question="Сколько дней на прекращение обработки?",
        text="Три рабочих дня.",
        citations=(RecordedCitation(anchor="st-21/ch-5", quote="не позднее трёх рабочих дней"),),
        model="recorded",
    )
    with pytest.raises(UngroundedAnswerError):
        await container.questions.record(access, invented)
