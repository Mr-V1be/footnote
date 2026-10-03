"""Organization administration: members, workspaces with roles, the audit log."""

from __future__ import annotations

import csv
import io

import anyio
import httpx

from snoska.bootstrap.container import Container
from tests.support.fakes import FakeDirectory
from tests.support.scenario import ALICE, BOB, EVA, LEO, OLGA, ORG_A, auth, run_jobs
from tests.support.tokens import TokenFactory

BASE = "/api/v1/organizations/alpha"
DEMO = anyio.Path(__file__).parents[2] / "demo" / "documents" / "polyarnaya-zvezda"


async def upload(api: httpx.AsyncClient, tokens: TokenFactory, workspace: str) -> str:
    content = await (DEMO / "soglasie-pokupatelya.docx").read_bytes()
    created = await api.post(
        f"{BASE}/workspaces/{workspace}/documents",
        headers=auth(tokens, ALICE),
        files={"file": ("soglasie.docx", content, "application/octet-stream")},
        data={"kind": "pd_consent"},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["documentId"])


async def test_a_restricted_workspace_admits_only_its_members(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    created = await api.post(
        f"{BASE}/workspaces",
        headers=auth(tokens, ALICE),
        json={"name": "Кадры", "slug": "hr", "restricted": True},
    )
    assert created.status_code == 201, created.text
    workspace_id = created.json()["id"]
    document_id = await upload(api, tokens, "hr")
    await run_jobs(container)

    # Eva (executor) is not listed: the workspace and its document do not exist for her.
    listed = await api.get(f"{BASE}/workspaces", headers=auth(tokens, EVA))
    assert [item["slug"] for item in listed.json()] == ["main"]
    hidden = await api.get(f"{BASE}/documents/{document_id}", headers=auth(tokens, EVA))
    assert hidden.status_code == 404

    # Listed as an observer there, she reads but cannot run a check.
    granted = await api.put(
        f"{BASE}/workspaces/{workspace_id}/members/{EVA.user_id}",
        headers=auth(tokens, ALICE),
        json={"role": "observer"},
    )
    assert granted.status_code == 200, granted.text
    document = await api.get(f"{BASE}/documents/{document_id}", headers=auth(tokens, EVA))
    assert document.status_code == 200
    assert "checks.run" not in document.json()["permissions"]
    refused = await api.post(
        f"{BASE}/documents/{document_id}/versions/1/checks", headers=auth(tokens, EVA)
    )
    assert refused.status_code == 403

    # Olga, an observer of the organization, becomes a lawyer in this workspace only.
    await api.put(
        f"{BASE}/workspaces/{workspace_id}/members/{OLGA.user_id}",
        headers=auth(tokens, ALICE),
        json={"role": "lawyer"},
    )
    olga = await api.get(f"{BASE}/documents/{document_id}", headers=auth(tokens, OLGA))
    assert "findings.decide" in olga.json()["permissions"]
    main = await api.get(f"{BASE}/workspaces", headers=auth(tokens, OLGA))
    roles = {item["slug"]: item["role"] for item in main.json()}
    assert roles == {"main": "observer", "hr": "lawyer"}


async def test_only_an_owner_administers_and_an_owner_always_remains(
    api: httpx.AsyncClient, tokens: TokenFactory, directory: FakeDirectory
) -> None:
    refused = await api.get(f"{BASE}/members", headers=auth(tokens, LEO))
    assert refused.status_code == 403

    invited = await api.post(
        f"{BASE}/members",
        headers=auth(tokens, ALICE),
        json={
            "email": "nina@alpha.example",
            "firstName": "Нина",
            "lastName": "П",
            "role": "executor",
        },
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["pending"] is True
    nina = invited.json()["userId"]

    promoted = await api.patch(
        f"{BASE}/members/{nina}", headers=auth(tokens, ALICE), json={"role": "lawyer"}
    )
    assert promoted.json()["role"] == "lawyer"
    unknown = await api.patch(
        f"{BASE}/members/{nina}", headers=auth(tokens, ALICE), json={"role": "admin"}
    )
    assert unknown.status_code == 422

    last_owner = await api.patch(
        f"{BASE}/members/{ALICE.user_id}", headers=auth(tokens, ALICE), json={"role": "lawyer"}
    )
    assert last_owner.status_code == 409
    assert last_owner.json()["code"] == "last_owner"

    removed = await api.delete(f"{BASE}/members/{nina}", headers=auth(tokens, ALICE))
    assert removed.status_code == 204
    assert all(str(member.user_id) != nina for member in await directory.list_members(ORG_A.id))


async def test_the_audit_log_records_who_did_what_and_exports_it(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    document_id = await upload(api, tokens, "main")
    await run_jobs(container)
    await api.post(f"{BASE}/documents/{document_id}/versions/1/checks", headers=auth(tokens, ALICE))
    await api.post(
        f"{BASE}/workspaces",
        headers=auth(tokens, ALICE),
        json={"name": "Договоры", "slug": "contracts"},
    )

    log = await api.get(f"{BASE}/audit", headers=auth(tokens, LEO))
    assert log.status_code == 200
    actions = [item["action"] for item in log.json()["items"]]
    assert actions == ["workspace.created", "check.requested", "document.uploaded"]
    entry = log.json()["items"][-1]
    assert entry["actor"]["label"] == ALICE.name
    assert entry["target"]["type"] == "document"

    only_documents = await api.get(
        f"{BASE}/audit", headers=auth(tokens, LEO), params={"category": "document"}
    )
    assert [item["action"] for item in only_documents.json()["items"]] == ["document.uploaded"]

    exported = await api.get(f"{BASE}/audit/export", headers=auth(tokens, ALICE))
    assert exported.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(exported.text.lstrip("\ufeff"))))
    assert rows[0][0] == "occurred_at"
    assert len(rows) == 4

    assert (await api.get(f"{BASE}/audit", headers=auth(tokens, EVA))).status_code == 403
    other = await api.get("/api/v1/organizations/beta/audit", headers=auth(tokens, BOB))
    assert other.json()["items"] == []


async def test_the_administration_catalog_lists_what_screens_choose_from(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    response = await api.get("/api/v1/administration/catalog", headers=auth(tokens, EVA))
    assert response.status_code == 200
    body = response.json()
    assert [role["code"] for role in body["roles"]] == ["owner", "lawyer", "executor", "observer"]
    assert "members.manage" in body["roles"][0]["permissions"]
    assert "ping" not in body["webhookEvents"]
    assert body["auditCategories"][0] == "document"
    assert "api_key" in body["actorKinds"]
