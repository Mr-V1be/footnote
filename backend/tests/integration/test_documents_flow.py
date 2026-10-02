"""Upload → background parsing → structure, with idempotency and versions."""

from __future__ import annotations

from pathlib import Path

import anyio
import httpx
import pytest

from snoska.bootstrap.container import Container
from tests.support.scenario import ALICE, ORG_A, auth, run_jobs
from tests.support.tokens import TokenFactory

pytestmark = pytest.mark.integration
DEMO = Path(__file__).parents[2] / "demo" / "documents" / "polyarnaya-zvezda"
BASE = f"/api/v1/organizations/{ORG_A.alias}"


async def upload(
    api: httpx.AsyncClient, tokens: TokenFactory, path: Path, key: str | None = None
) -> httpx.Response:
    headers = auth(tokens, ALICE) | ({"Idempotency-Key": key} if key else {})
    content = await anyio.Path(path).read_bytes()
    return await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=headers,
        files={"file": (path.name, content, "application/octet-stream")},
        data={"kind": "pd_policy"},
    )


async def test_uploaded_document_is_parsed_in_background(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> None:
    created = await upload(api, tokens, DEMO / "politika-obrabotki-pd.docx")
    assert created.status_code == 201
    document_id = created.json()["documentId"]

    queued = await api.get(
        f"{BASE}/documents/{document_id}/versions/1/structure", headers=auth(tokens, ALICE)
    )
    assert queued.json()["version"]["status"] == "queued"
    assert queued.json()["blocks"] == []

    # Parsing, then the checks it schedules for the parsed version.
    assert await run_jobs(container) == 2
    parsed = (
        await api.get(
            f"{BASE}/documents/{document_id}/versions/1/structure", headers=auth(tokens, ALICE)
        )
    ).json()
    assert parsed["version"]["status"] == "parsed"
    assert parsed["version"]["method"] == "docx"
    assert any(entry["text"] == "Общие положения" for entry in parsed["outline"])
    assert {r["kind"] for r in parsed["requisites"]} >= {"approval_stamp", "date", "document_type"}

    original = await api.get(
        f"{BASE}/documents/{document_id}/versions/1/file", headers=auth(tokens, ALICE)
    )
    assert original.content == (DEMO / "politika-obrabotki-pd.docx").read_bytes()


async def test_retried_upload_with_same_key_is_not_duplicated(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    first = await upload(api, tokens, DEMO / "soglasie-pokupatelya.docx", key="attempt-1")
    second = await upload(api, tokens, DEMO / "soglasie-pokupatelya.docx", key="attempt-1")
    assert first.json()["documentId"] == second.json()["documentId"]
    assert (first.json()["created"], second.json()["created"]) == (True, False)
    listing = await api.get(f"{BASE}/workspaces/main/documents", headers=auth(tokens, ALICE))
    assert len(listing.json()["items"]) == 1


async def test_versions_are_numbered_and_identical_files_rejected(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> None:
    created = await upload(api, tokens, DEMO / "polozhenie-o-pd-rabotnikov.docx")
    document_id = created.json()["documentId"]
    revised = DEMO / "polozhenie-o-pd-rabotnikov-red2.docx"
    second = await api.post(
        f"{BASE}/documents/{document_id}/versions",
        headers=auth(tokens, ALICE),
        files={"file": (revised.name, revised.read_bytes(), "application/octet-stream")},
    )
    assert second.json()["versionNumber"] == 2
    same = await api.post(
        f"{BASE}/documents/{document_id}/versions",
        headers=auth(tokens, ALICE),
        files={"file": (revised.name, revised.read_bytes(), "application/octet-stream")},
    )
    assert (same.status_code, same.json()["code"]) == (409, "version_unchanged")
    await run_jobs(container)
    details = (await api.get(f"{BASE}/documents/{document_id}", headers=auth(tokens, ALICE))).json()
    assert details["latestVersion"] == 2
    assert [v["status"] for v in details["versions"]] == ["parsed", "parsed"]


async def test_unsupported_and_oversized_files_are_refused(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    renamed = await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=auth(tokens, ALICE),
        files={"file": ("virus.pdf", b"MZ\x90\x00binary", "application/pdf")},
    )
    assert (renamed.status_code, renamed.json()["code"]) == (422, "unsupported_format")
    limit = container.settings.max_upload_bytes
    huge = await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=auth(tokens, ALICE),
        files={"file": ("big.pdf", b"%PDF-1.7" + b"0" * (limit + 1), "application/pdf")},
    )
    assert (huge.status_code, huge.json()["code"]) == (413, "file_too_large")


async def test_listing_is_paginated_by_keyset(api: httpx.AsyncClient, tokens: TokenFactory) -> None:
    for index, name in enumerate(
        [
            "politika-obrabotki-pd.docx",
            "soglasie-pokupatelya.docx",
            "polozhenie-o-pd-rabotnikov.docx",
        ]
    ):
        await upload(api, tokens, DEMO / name, key=f"page-{index}")
    first = (
        await api.get(f"{BASE}/workspaces/main/documents?limit=2", headers=auth(tokens, ALICE))
    ).json()
    second = (
        await api.get(
            f"{BASE}/workspaces/main/documents?limit=2&cursor={first['nextCursor']}",
            headers=auth(tokens, ALICE),
        )
    ).json()
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(ids) == len(set(ids)) == 3
    assert second["nextCursor"] is None
    found = (
        await api.get(f"{BASE}/workspaces/main/documents?q=SOGLASIE", headers=auth(tokens, ALICE))
    ).json()
    assert [item["title"] for item in found["items"]] == ["soglasie-pokupatelya"]
