"""Tenant isolation: enforced by the database (RLS) and visible through the API."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from docx import Document
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from snoska.bootstrap.container import Container
from snoska.domain.documents.document import Document as DocumentEntity
from snoska.domain.tenancy.organization import Organization, Workspace
from snoska.infrastructure.persistence.unit_of_work import SqlUnitOfWorkFactory
from tests.support.scenario import ALICE, BOB, OLGA, ORG_A, ORG_B, auth
from tests.support.tokens import TokenFactory

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 2, tzinfo=UTC)


def docx_bytes(text_value: str) -> bytes:
    document = Document()
    document.add_paragraph(text_value)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def _seed_tenant(uow: SqlUnitOfWorkFactory, org_id: UUID, alias: str) -> DocumentEntity:
    workspace = Workspace(
        id=uuid4(), organization_id=org_id, slug="main", name="Основное", created_at=NOW
    )
    document = DocumentEntity.register(
        id=uuid4(),
        organization_id=org_id,
        workspace_id=workspace.id,
        title=f"Документ {alias}",
        kind_code="other",
        created_by=uuid4(),
        now=NOW,
    )
    async with uow.for_tenant(org_id) as tx:
        await tx.organizations.add_if_absent(Organization(org_id, alias, alias, NOW))
        await tx.workspaces.add_if_absent(workspace)
        await tx.documents.add(document)
        await tx.commit()
    return document


async def test_rows_of_another_tenant_are_invisible_to_queries(container: Container) -> None:
    uow = SqlUnitOfWorkFactory(container.engine)
    doc_a = await _seed_tenant(uow, ORG_A.id, ORG_A.alias)
    doc_b = await _seed_tenant(uow, ORG_B.id, ORG_B.alias)

    async with uow.for_tenant(ORG_A.id) as tx:
        assert await tx.documents.get(doc_a.id) is not None
        assert await tx.documents.get(doc_b.id) is None
        assert [ws.organization_id for ws in await tx.workspaces.list()] == [ORG_A.id]

    async with container.engine.connect() as connection:
        visible = await connection.scalar(text("SELECT count(*) FROM documents"))
    assert visible == 0, "without a tenant context no tenant rows are visible"


async def test_writing_into_another_tenant_is_rejected_by_the_database(
    container: Container,
) -> None:
    async with container.engine.connect() as connection:
        await connection.execute(
            text("SELECT set_config('snoska.tenant_id', :tenant, true)"), {"tenant": str(ORG_A.id)}
        )
        with pytest.raises(DBAPIError, match="row-level security"):
            await connection.execute(
                text(
                    "INSERT INTO workspaces (id, organization_id, slug, name, created_at) "
                    "VALUES (:id, :org, 'stolen', 'Чужое', now())"
                ),
                {"id": str(uuid4()), "org": str(ORG_B.id)},
            )


async def test_runtime_role_cannot_bypass_row_level_security(container: Container) -> None:
    async with container.engine.connect() as connection:
        row = (
            await connection.execute(
                text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")
            )
        ).one()
        owners = await connection.scalar(
            text(
                "SELECT count(*) FROM pg_tables "
                "WHERE tablename = 'documents' AND tableowner = current_user"
            )
        )
    assert (row.rolbypassrls, row.rolsuper, owners) == (False, False, 0)


async def test_api_never_crosses_tenants(api: httpx.AsyncClient, tokens: TokenFactory) -> None:
    upload = await api.post(
        f"/api/v1/organizations/{ORG_A.alias}/workspaces/main/documents",
        headers=auth(tokens, ALICE),
        files={"file": ("politika.docx", docx_bytes("Политика"), "application/octet-stream")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["documentId"]

    # A member of another organization can neither enter the organization...
    foreign = await api.get(
        f"/api/v1/organizations/{ORG_A.alias}/documents/{document_id}", headers=auth(tokens, BOB)
    )
    assert (foreign.status_code, foreign.json()["code"]) == (403, "not_a_member")
    # ...nor reach the document through their own organization.
    sideways = await api.get(
        f"/api/v1/organizations/{ORG_B.alias}/documents/{document_id}", headers=auth(tokens, BOB)
    )
    assert (sideways.status_code, sideways.json()["code"]) == (404, "document_not_found")
    listing = await api.get(
        f"/api/v1/organizations/{ORG_B.alias}/workspaces/main/documents", headers=auth(tokens, BOB)
    )
    assert listing.json()["items"] == []

    own = await api.get(
        f"/api/v1/organizations/{ORG_A.alias}/workspaces/main/documents",
        headers=auth(tokens, ALICE),
    )
    assert [item["id"] for item in own.json()["items"]] == [document_id]


async def test_roles_are_enforced_by_the_server(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    refused = await api.post(
        f"/api/v1/organizations/{ORG_A.alias}/workspaces/main/documents",
        headers=auth(tokens, OLGA),
        files={"file": ("a.docx", docx_bytes("x"), "application/octet-stream")},
    )
    assert (refused.status_code, refused.json()["code"]) == (403, "missing_permission")
    readable = await api.get(
        f"/api/v1/organizations/{ORG_A.alias}/workspaces/main/documents", headers=auth(tokens, OLGA)
    )
    assert readable.status_code == 200


async def test_requests_without_valid_token_are_unauthenticated(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    anonymous = await api.get("/api/v1/me")
    assert (anonymous.status_code, anonymous.json()["code"]) == (401, "unauthenticated")
    forged = await api.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {TokenFactory().token(ALICE)}"}
    )
    assert forged.status_code == 401
    me = await api.get("/api/v1/me", headers=auth(tokens, ALICE))
    assert [m["organization"]["alias"] for m in me.json()["memberships"]] == [ORG_A.alias]
    assert me.json()["memberships"][0]["role"] == "owner"
