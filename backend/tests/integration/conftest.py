"""Integration tests run against PostgreSQL (database ``snoska_test``).

The schema is migrated once per session as the owner role; every test
starts from empty tables. The API is exercised in-process with test
doubles only for providers outside the database: token keys, the
organization directory and the embedding model.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import text

os.environ.setdefault("FOOTNOTE_DB_NAME", "snoska_test")

from footnote.api.app import create_app
from footnote.bootstrap.container import Container, Overrides, build_container
from footnote.bootstrap.settings import (
    BACKEND_ROOT,
    AiProvider,
    AiSettings,
    Settings,
    StorageBackend,
)
from footnote.domain.corpus.embedding import EmbeddingSpace
from footnote.infrastructure.persistence.database import DatabaseConfig, create_engine
from footnote.infrastructure.persistence.vector_index import ensure_space
from tests.support.fakes import (
    FakeDirectory,
    HashEmbedder,
    RecordedLanguageModel,
    RecordingTransport,
)
from tests.support.scenario import MEMBERS, ORG_A, ORG_B, member_of
from tests.support.tokens import ISSUER, StaticKeys, TokenFactory

TABLES = (
    "model_completions, edition_checks, task_states, conversation_turns, conversations, "
    "version_changes, payment_events, invoices, usage_ledger, subscriptions, "
    "webhook_deliveries, webhook_endpoints, api_keys, audit_events, workspace_members, "
    "findings, check_results, check_runs, text_embeddings, edition_indexes, "
    "document_blocks, document_structures, document_versions, documents, workspaces, "
    "organizations, user_profiles, outbox_messages, norm_embeddings, norm_units, "
    "corpus_editions, legal_acts"
)
TEST_PLANS = Path(__file__).parents[1] / "support" / "data" / "plans.yaml"
# A small space for the deterministic test embedder, registered like any model's.
TEST_SPACE = EmbeddingSpace("test-hash-64", 64)
# Verdicts of the recorded language model by words of a check's question.
RECORDED_VERDICTS = {
    "трансграничную передачу": "absent",
    "уничтожения персональных данных": "partial",
    "права субъекта": "uncertain",
}


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    base = Settings()
    assert base.database.name.endswith("_test"), "integration tests need a dedicated database"
    keycloak = base.keycloak.model_copy(update={"url": ISSUER.removesuffix("/realms/snoska")})
    # Files of a test run stay in a temporary directory, whatever the stand uses.
    storage = base.storage.model_copy(
        update={
            "storage_backend": StorageBackend.LOCAL,
            "storage_root": Path(tmp_path_factory.mktemp("blobs")),
        }
    )
    integrations = base.integrations.model_copy(
        update={"secrets_key": SecretStr("test-secrets-key"), "webhooks_allow_private": True}
    )
    billing = base.billing.model_copy(update={"plans": TEST_PLANS})
    payments = base.payments.model_copy(update={"test_secret": SecretStr("test-payments")})
    # Tests never reach a real model, whatever the stand's .env configures.
    ai = AiSettings(_env_file=None, ai_provider=AiProvider.NONE)
    # Measurements of a test run go to a copy of the published one.
    quality = Path(tmp_path_factory.mktemp("quality"))
    (quality / "benchmark.json").write_bytes(base.checks.quality_report.read_bytes())
    checks = base.checks.model_copy(
        update={"quality_report": quality / "benchmark.json", "model_trials": quality / "models"}
    )
    return base.model_copy(
        update={
            "checks": checks,
            "keycloak": keycloak,
            "storage": storage,
            "integrations": integrations,
            "billing": billing,
            "payments": payments,
            "ai": ai,
        }
    )


def _owner(settings: Settings) -> DatabaseConfig:
    db = settings.database
    return DatabaseConfig(
        db.host, db.port, db.name, db.owner_user, db.owner_password.get_secret_value()
    )


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


@pytest.fixture(scope="session", autouse=True)
def migrated(alembic_config: Config, settings: Settings) -> None:
    command.upgrade(alembic_config, "head")


@pytest.fixture(autouse=True)
async def test_space(migrated: None, settings: Settings) -> None:
    engine = create_engine(_owner(settings))
    try:
        await ensure_space(engine, TEST_SPACE)
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_database(settings: Settings) -> None:
    engine = create_engine(_owner(settings))
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await engine.dispose()


@pytest.fixture(scope="session")
def tokens() -> TokenFactory:
    return TokenFactory()


@pytest.fixture
def directory() -> FakeDirectory:
    """The organizations and their members, with the scenario's members in place."""
    fake = FakeDirectory([ORG_A, ORG_B])
    for identity in MEMBERS:
        for organization_id, roles in identity.organizations.values():
            fake.add(organization_id, member_of(identity, roles))
    return fake


@pytest.fixture
def receiver() -> RecordingTransport:
    """Where webhooks go in tests: answers 204 unless a test says otherwise."""
    return RecordingTransport(204)


@pytest.fixture
async def container(
    settings: Settings, tokens: TokenFactory, directory: FakeDirectory, receiver: RecordingTransport
) -> AsyncIterator[Container]:
    built = await build_container(
        settings,
        overrides=Overrides(
            key_source=StaticKeys(tokens),
            directory=directory,
            administration=directory,
            webhook_transport=receiver,
            embedder=HashEmbedder(TEST_SPACE),
            language_model=RecordedLanguageModel(RECORDED_VERDICTS),
        ),
    )
    yield built
    await built.close()


@pytest.fixture
async def api(container: Container, settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    app.state.container = container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
        yield client
