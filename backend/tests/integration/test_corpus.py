"""Corpus: snapshot ingestion, embedding into pgvector, retrieval, migrations."""

from __future__ import annotations

import httpx
import pytest
from alembic import command
from alembic.config import Config

from snoska.application.corpus.sync import SyncOutcome
from snoska.application.shared.jobs import INDEX_CORPUS_EDITION
from snoska.bootstrap.container import Container
from snoska.domain.corpus.assembly import embedding_texts_for
from tests.support.scenario import ALICE, auth, run_jobs
from tests.support.tokens import TokenFactory

pytestmark = pytest.mark.integration


async def test_snapshot_is_ingested_once_served_and_searchable_once_indexed(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> None:
    first = await container.corpus_sync.sync("152-fz", "snapshot")
    again = await container.corpus_sync.sync("152-fz", "snapshot")
    assert (first.outcome, again.outcome) == (SyncOutcome.INGESTED, SyncOutcome.UNCHANGED)
    assert first.unit_count > 300

    acts = (await api.get("/api/v1/corpus/acts", headers=auth(tokens, ALICE))).json()
    assert acts[0]["edition"]["sourceRevision"] == first.source_revision, "served at once"
    unindexed = await api.get(
        "/api/v1/corpus/search", params={"q": "согласие"}, headers=auth(tokens, ALICE)
    )
    assert unindexed.status_code == 409
    assert unindexed.json()["code"] == "corpus_not_indexed", "never searched half-indexed"

    assert await run_jobs(container) == 1

    units = (await api.get("/api/v1/corpus/acts/152-fz/units", headers=auth(tokens, ALICE))).json()
    clause = next(u for u in units["units"] if u["anchor"] == "st-18.1/ch-1/p-2")
    assert clause["citation"] == "п. 2 ч. 1 ст. 18.1 152-ФЗ"

    # The hash embedder maps equal passages to equal vectors: searching for a
    # stored passage must return exactly that provision first.
    handler_texts = await _passage_of(container, clause["id"])
    hits = (
        await api.get(
            "/api/v1/corpus/search", params={"q": handler_texts}, headers=auth(tokens, ALICE)
        )
    ).json()["hits"]
    assert hits[0]["unit"]["anchor"] == "st-18.1/ch-1/p-2"
    assert hits[0]["similarity"] == pytest.approx(1.0, abs=1e-6)
    assert hits[0]["articleHeading"].startswith("Статья 18.1.")


async def _passage_of(container: Container, unit_id: str) -> str:
    edition = (await container.corpus.acts())[0].active_edition
    assert edition is not None
    content = await container.corpus.active_content("152-fz")
    unit = next(u for u in content.units if str(u.id) == unit_id)
    assert unit.embedding_sha256 is not None
    return embedding_texts_for(content.units)[unit.embedding_sha256]


async def test_indexing_job_is_idempotent(container: Container) -> None:
    result = await container.corpus_sync.sync("152-fz", "snapshot")
    handler = container.job_handlers[INDEX_CORPUS_EDITION.name]
    await handler({"edition_id": str(result.edition_id)})
    await handler({"edition_id": str(result.edition_id)})
    assert await container.corpus_indexing.index(result.edition_id) == 0, "nothing left to embed"
    [overview] = await container.corpus.acts()
    assert overview.active_edition is not None
    assert overview.active_edition.id == result.edition_id


def test_migrations_roll_back_and_forward(alembic_config: Config) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
