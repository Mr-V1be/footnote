"""The demo stand: a nightly reset clears one tenant only, and the accounts
of one-click sign-in keep their roles."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import anyio
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from footnote.api.app import create_app
from footnote.application.operations.demo_reset import DemoStandReset
from footnote.bootstrap.container import Container, Overrides, build_container
from footnote.bootstrap.settings import DemoSettings, Settings
from footnote.domain.tenancy.members import Member
from footnote.infrastructure.persistence.database import DatabaseConfig, create_engine
from footnote.infrastructure.persistence.maintenance import OwnerBacklogProbe, OwnerTenantPurge
from tests.support.fakes import FakeDirectory
from tests.support.scenario import (
    ALICE,
    BOB,
    LEO,
    MEMBERS,
    ORG_A,
    auth,
    run_jobs,
)
from tests.support.tokens import MemberIdentity, StaticKeys, TokenFactory

DEMO = anyio.Path(__file__).parents[2] / "demo" / "documents" / "polyarnaya-zvezda"


async def upload(
    api: httpx.AsyncClient, tokens: TokenFactory, alias: str, who: MemberIdentity
) -> str:
    content = await (DEMO / "soglasie-pokupatelya.docx").read_bytes()
    created = await api.post(
        f"/api/v1/organizations/{alias}/workspaces/main/documents",
        headers=auth(tokens, who),
        files={"file": ("soglasie.docx", content, "application/octet-stream")},
        data={"kind": "pd_consent"},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["documentId"])


def owner_engine(settings: Settings) -> AsyncEngine:
    db = settings.database
    return create_engine(
        DatabaseConfig(
            db.host, db.port, db.name, db.owner_user, db.owner_password.get_secret_value()
        )
    )


async def test_a_reset_clears_one_organization_and_leaves_the_others(
    api: httpx.AsyncClient,
    tokens: TokenFactory,
    container: Container,
    settings: Settings,
    directory: FakeDirectory,
) -> None:
    await upload(api, tokens, "alpha", ALICE)
    kept = await upload(api, tokens, "beta", BOB)
    await run_jobs(container)
    await api.post(
        "/api/v1/organizations/alpha/api-keys",
        headers=auth(tokens, ALICE),
        json={"name": "Посетитель", "scopes": ["documents:read"]},
    )
    visitor = Member(
        user_id=uuid4(),
        email="visitor@alpha.example",
        first_name="Гость",
        last_name="Стенда",
        role_codes=frozenset({"observer"}),
        pending=True,
    )
    directory.add(ORG_A.id, visitor)
    alpha_files = [key async for key in container.blobs.keys(f"tenants/{ORG_A.id}/")]
    assert alpha_files

    engine = owner_engine(settings)
    try:
        reset = DemoStandReset(OwnerTenantPurge(engine), container.blobs, directory, directory)
        seeded = frozenset(member.email for member in MEMBERS if "alpha" in member.email)
        cleared = await reset.clear(ORG_A.id, seeded)
    finally:
        await engine.dispose()

    assert (cleared.files, cleared.removed_members) == (len(alpha_files), 1)
    assert [key async for key in container.blobs.keys(f"tenants/{ORG_A.id}/")] == []
    # The organization comes back empty on the next visit, the other one is untouched.
    listed = await api.get(
        "/api/v1/organizations/alpha/workspaces/main/documents", headers=auth(tokens, ALICE)
    )
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    audit = await api.get("/api/v1/organizations/alpha/audit", headers=auth(tokens, ALICE))
    assert audit.json()["items"] == []
    keys = await api.get("/api/v1/organizations/alpha/api-keys", headers=auth(tokens, ALICE))
    assert keys.json() == []
    other = await api.get(f"/api/v1/organizations/beta/documents/{kept}", headers=auth(tokens, BOB))
    assert other.status_code == 200


@pytest.fixture
async def demo_api(
    settings: Settings, tokens: TokenFactory, directory: FakeDirectory, tmp_path: Path
) -> AsyncIterator[httpx.AsyncClient]:
    (tmp_path / "seed.yaml").write_text(f"demo_login:\n  lawyer: {LEO.email}\n", encoding="utf-8")
    demo_settings = settings.model_copy(
        update={"demo": DemoSettings(mode=True), "demo_root": tmp_path}
    )
    container = await build_container(
        demo_settings,
        overrides=Overrides(
            key_source=StaticKeys(tokens), directory=directory, administration=directory
        ),
    )
    app = create_app(demo_settings)
    app.state.container = container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
        yield client
    await container.close()


async def test_a_demo_sign_in_account_keeps_its_role(
    demo_api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    refused = await demo_api.patch(
        f"/api/v1/organizations/alpha/members/{LEO.user_id}",
        headers=auth(tokens, ALICE),
        json={"role": "observer"},
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "demo_account_protected"
    removal = await demo_api.delete(
        f"/api/v1/organizations/alpha/members/{LEO.user_id}", headers=auth(tokens, ALICE)
    )
    assert removal.status_code == 409


async def test_the_backlog_counts_work_until_the_worker_is_done(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container, settings: Settings
) -> None:
    engine = owner_engine(settings)
    try:
        probe = OwnerBacklogProbe(engine)
        await upload(api, tokens, "alpha", ALICE)
        assert not (await probe.backlog()).idle
        await run_jobs(container)
        assert (await probe.backlog()).idle
    finally:
        await engine.dispose()
