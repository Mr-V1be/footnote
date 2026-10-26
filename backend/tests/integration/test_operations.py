"""The platform's own work: periodic tasks, the weekly corpus check, the
operator's console."""

from __future__ import annotations

from uuid import uuid4

import httpx
from sqlalchemy import text

from footnote.application.operations.corpus_watch import WatchCorpusEditions
from footnote.bootstrap.container import Container
from footnote.domain.operations.schedule import WatchOutcome
from footnote.infrastructure.corpus_sources.catalog import YamlActCatalog
from footnote.ports.operations.notifications import Email, Recipient
from tests.support.scenario import ALICE, ORG_A, auth, run_jobs
from tests.support.tokens import MemberIdentity, TokenFactory

OPERATOR = MemberIdentity(
    user_id=uuid4(),
    email="operator@platform.example",
    name="Оператор",
    organizations={},
    realm_roles=("platform-admin",),
)


class Inbox:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    async def send(self, email: Email) -> None:
        self.sent.append(email)


class Admins:
    async def recipients(self) -> list[Recipient]:
        return [Recipient(OPERATOR.user_id, OPERATOR.email)]


def watch(container: Container, inbox: Inbox) -> WatchCorpusEditions:
    return WatchCorpusEditions(
        container.corpus_watch._uow_factory,
        YamlActCatalog(container.settings.corpus_catalog),
        container.corpus_sync,
        Admins(),
        inbox,
        container.corpus_watch._clock,
        web_url="http://web.test",
        source="snapshot",
    )


async def test_a_new_edition_is_loaded_and_the_operator_told_once(container: Container) -> None:
    inbox = Inbox()
    job = watch(container, inbox)
    [first] = await job.run()
    [second] = await job.run()
    assert (first.outcome, second.outcome) == (WatchOutcome.NEW_EDITION, WatchOutcome.UNCHANGED)
    [email] = inbox.sent
    assert email.to == (OPERATOR.email,)
    assert "новая редакция" in email.text
    assert "footnote checks recheck" in email.text


async def test_the_notice_is_written_in_the_language_the_operator_last_used(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    await api.get("/api/v1/me", headers={**auth(tokens, OPERATOR), "Accept-Language": "en"})
    inbox = Inbox()
    await watch(container, inbox).run()
    [email] = inbox.sent
    assert email.subject == "Snoska: a new edition of a law in the corpus"
    assert "152-FZ: the portal has a new edition" in email.text


async def test_periodic_tasks_are_queued_once_when_due(container: Container) -> None:
    await container.scheduler.register()
    assert await container.scheduler.tick() == 2, "the weekly watch and the hourly resume"
    assert await container.scheduler.tick() == 0, "neither is due again yet"
    async with container.engine.begin() as connection:
        jobs = (
            (
                await connection.execute(
                    text("SELECT job_name FROM outbox_messages WHERE dispatched_at IS NULL")
                )
            )
            .scalars()
            .all()
        )
    assert sorted(jobs) == ["checks.resume", "corpus.watch"]


async def test_the_operator_sees_organizations_and_moves_them_between_plans(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    await api.get("/api/v1/organizations/alpha/workspaces", headers=auth(tokens, ALICE))
    refused = await api.get("/api/v1/platform/system", headers=auth(tokens, ALICE))
    assert refused.status_code == 403

    operator = auth(tokens, OPERATOR)
    rows = (await api.get("/api/v1/platform/organizations/overview", headers=operator)).json()
    assert [row["alias"] for row in rows] == ["alpha"]
    assert rows[0]["planCode"] == "start"
    moved = await api.put(
        f"/api/v1/platform/organizations/{ORG_A.id}/plan", headers=operator, json={"plan": "team"}
    )
    assert moved.status_code == 204
    billing = (
        await api.get("/api/v1/organizations/alpha/billing", headers=auth(tokens, ALICE))
    ).json()
    assert billing["plan"]["code"] == "team"

    system = (await api.get("/api/v1/platform/system", headers=operator)).json()
    health = {item["name"]: item["ok"] for item in system["health"]}
    assert health["database"] is True
    assert {"storage", "queue", "identity"} <= set(health)
    assert system["modelConfigured"] is False
    await run_jobs(container)
