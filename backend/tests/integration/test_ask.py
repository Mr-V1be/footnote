"""«Спросить норму»: answers that quote the corpus, or say the norm is silent."""

from __future__ import annotations

import httpx

from snoska.api.app import create_app
from snoska.bootstrap.container import Container, Overrides, build_container
from snoska.bootstrap.settings import Settings
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
