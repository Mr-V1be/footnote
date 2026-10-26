"""Automatic correction of formatting: a new version with a journal."""

from __future__ import annotations

import anyio
import httpx

from footnote.bootstrap.container import Container
from tests.support.scenario import ALICE, OLGA, auth, run_jobs
from tests.support.tokens import TokenFactory

BASE = "/api/v1/organizations/alpha"
REFERENCE = anyio.Path(__file__).parents[2] / "demo" / "reference"


async def checked(api: httpx.AsyncClient, tokens: TokenFactory, container: Container) -> str:
    content = await (REFERENCE / "politika-zarya.docx").read_bytes()
    created = await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=auth(tokens, ALICE),
        files={"file": ("politika.docx", content, "application/octet-stream")},
        data={"kind": "pd_policy"},
    )
    await run_jobs(container)
    return str(created.json()["documentId"])


def statuses(report: dict) -> dict[str, str]:  # type: ignore[type-arg]
    return {result["checkCode"]: result["status"] for result in report["results"]}


async def test_formatting_is_corrected_into_a_new_version(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    document = await checked(api, tokens, container)
    versions = f"{BASE}/documents/{document}/versions"
    preview = (await api.get(f"{versions}/1/autofix", headers=auth(tokens, ALICE))).json()
    planned = {item["checkCode"] for item in preview["planned"]}
    assert {"formatting.page_margins", "formatting.font_size", "formatting.date_format"} <= planned
    skipped = {item["checkCode"]: item["reason"] for item in preview["skipped"]}
    assert skipped["formatting.approval_stamp"] == "needs_person"

    assert (await api.post(f"{versions}/1/autofix", headers=auth(tokens, OLGA))).status_code == 403
    applied = await api.post(f"{versions}/1/autofix", headers=auth(tokens, ALICE))
    assert applied.status_code == 201, applied.text
    assert applied.json()["version"] == 2
    journal = {item["checkCode"]: item for item in applied.json()["changes"]}
    assert journal["formatting.date_format"]["before"] == "1.2.2026"
    assert journal["formatting.date_format"]["after"] == "01.02.2026"
    assert "left=15" in journal["formatting.page_margins"]["before"]
    assert journal["formatting.font_size"]["places"] > 1
    # Each line says what it measures, so its values are read with units.
    assert journal["formatting.page_margins"]["kind"] == "margins"
    assert journal["formatting.font_size"]["kind"] == "font_size"
    assert journal["formatting.date_format"]["kind"] == "text"

    details = (await api.get(f"{BASE}/documents/{document}", headers=auth(tokens, ALICE))).json()
    second = next(item for item in details["versions"] if item["number"] == 2)
    assert (second["origin"], second["derivedFrom"]) == ("autofix", 1)
    stored = await api.get(f"{versions}/2/changes", headers=auth(tokens, ALICE))
    assert len(stored.json()) == len(applied.json()["changes"])

    # The new version is checked like an upload: what was corrected now passes.
    await run_jobs(container)
    report = (await api.get(f"{versions}/2/checks/latest", headers=auth(tokens, ALICE))).json()
    result = statuses(report)
    assert result["formatting.page_margins"] == "passed"
    assert result["formatting.font_size"] == "passed"
    assert result["formatting.date_format"] == "passed"
    assert result["formatting.approval_stamp"] == "violation", "a person has to add it"
    original = (await api.get(f"{versions}/1/checks/latest", headers=auth(tokens, ALICE))).json()
    assert statuses(original)["formatting.font_size"] == "violation", "the source is kept"

    log = (await api.get(f"{BASE}/audit", headers=auth(tokens, ALICE))).json()["items"]
    assert any(item["action"] == "document.autofixed" for item in log)
