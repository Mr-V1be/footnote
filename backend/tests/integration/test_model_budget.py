"""A free model allows few requests a day: a document's legal checks share
one request, a spent allowance leaves an honest state, and the checks run
again once it renews."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta

import anyio
import httpx
import pytest

from snoska.api.app import create_app
from snoska.bootstrap.container import Container, Overrides, build_container
from snoska.bootstrap.settings import Settings
from snoska.infrastructure.ai.budget import UnlimitedBudget
from snoska.infrastructure.ai.cache import CachingLanguageModel
from snoska.infrastructure.persistence.repositories.completions import PostgresCompletionCache
from snoska.infrastructure.system.clock import SystemClock
from snoska.ports.ai import (
    ChatMessage,
    Completion,
    CompletionRequest,
    MessageRole,
    ModelBudgetExhaustedError,
)
from tests.integration.conftest import RECORDED_VERDICTS, TEST_SPACE
from tests.support.fakes import FakeDirectory, HashEmbedder, RecordedLanguageModel
from tests.support.scenario import ALICE, auth, run_jobs
from tests.support.tokens import StaticKeys, TokenFactory

DEMO = anyio.Path(__file__).parents[2] / "demo" / "documents" / "polyarnaya-zvezda"
BASE = "/api/v1/organizations/alpha"


class AllowanceModel:
    """A model whose daily allowance can run out: refuses while ``spent``."""

    def __init__(self) -> None:
        self.inner = RecordedLanguageModel(RECORDED_VERDICTS)
        self.model = self.inner.model
        self.spent = False

    async def complete(self, request: CompletionRequest) -> Completion:
        if self.spent:
            raise ModelBudgetExhaustedError("today's requests are spent")
        return await self.inner.complete(request)


@pytest.fixture
def model() -> AllowanceModel:
    return AllowanceModel()


@pytest.fixture
async def stand(
    settings: Settings, tokens: TokenFactory, directory: FakeDirectory, model: AllowanceModel
) -> AsyncIterator[tuple[Container, httpx.AsyncClient]]:
    container = await build_container(
        settings,
        overrides=Overrides(
            key_source=StaticKeys(tokens),
            directory=directory,
            administration=directory,
            embedder=HashEmbedder(TEST_SPACE),
            language_model=model,
        ),
    )
    app = create_app(settings)
    app.state.container = container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
        yield container, client
    await container.close()


async def upload(api: httpx.AsyncClient, tokens: TokenFactory) -> str:
    content = await (DEMO / "politika-obrabotki-pd.docx").read_bytes()
    created = await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=auth(tokens, ALICE),
        files={"file": ("politika.docx", content, "application/octet-stream")},
        data={"kind": "pd_policy"},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["documentId"])


def model_results(report: dict) -> list[dict]:  # type: ignore[type-arg]
    return [result for result in report["results"] if result["method"] == "model"]


async def test_legal_checks_share_a_request_wait_for_the_allowance_and_resume(
    stand: tuple[Container, httpx.AsyncClient], tokens: TokenFactory, model: AllowanceModel
) -> None:
    container, api = stand
    await container.corpus_sync.sync("152-fz", "snapshot")
    await run_jobs(container)
    model.spent = True
    document = await upload(api, tokens)
    await run_jobs(container)
    latest = f"{BASE}/documents/{document}/versions/1/checks/latest"
    waiting = (await api.get(latest, headers=auth(tokens, ALICE))).json()
    assert waiting["run"]["status"] == "completed", "rules still run, the check does not fail"
    assert {result["errorCode"] for result in model_results(waiting)} == {"model_daily_limit"}

    # The allowance renews: the hourly job checks the document again.
    model.spent = False
    assert await container.recheck.waiting_for_model(UnlimitedBudget()) == 1
    await run_jobs(container)
    resumed = (await api.get(latest, headers=auth(tokens, ALICE))).json()
    statuses = {result["status"] for result in model_results(resumed)}
    assert "error" not in statuses
    legal = len(model_results(resumed))
    batches = -(-legal // container.settings.checks.checks_per_request)
    assert len(model.inner.requests) == batches, "one request per batch of requirements"
    assert await container.recheck.waiting_for_model(UnlimitedBudget()) == 0


async def test_an_answer_is_kept_by_its_request(container: Container) -> None:
    inner = RecordedLanguageModel(RECORDED_VERDICTS)
    cache = PostgresCompletionCache(container.engine, SystemClock(), timedelta(days=1))
    model = CachingLanguageModel(inner, cache, ("recorded",))
    request = CompletionRequest(
        messages=(ChatMessage(MessageRole.USER, "Требования:\n"),), response_schema=None
    )
    first = await model.complete(request)
    again = await model.complete(request)
    assert first.text == again.text
    assert len(inner.requests) == 1
