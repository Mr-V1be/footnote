"""Checks: run after parsing, grounded findings, review by role, isolation, progress."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import httpx
import pytest

from snoska.api.app import create_app
from snoska.bootstrap.container import Container, Overrides, build_container
from snoska.bootstrap.settings import Settings
from tests.integration.conftest import TEST_SPACE
from tests.support.fakes import FakeDirectory, HashEmbedder
from tests.support.scenario import ALICE, BOB, EVA, OLGA, ORG_A, ORG_B, auth, run_jobs
from tests.support.tokens import StaticKeys, TokenFactory

pytestmark = pytest.mark.integration
DEMO = Path(__file__).parents[2] / "demo" / "documents" / "polyarnaya-zvezda"
BASE = f"/api/v1/organizations/{ORG_A.alias}"


async def checked_policy(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> tuple[str, dict]:  # type: ignore[type-arg]
    """Ingest and index the law, upload a policy, run every job; the latest report."""
    await container.corpus_sync.sync("152-fz", "snapshot")
    content = await anyio.Path(DEMO / "politika-obrabotki-pd.docx").read_bytes()
    created = await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=auth(tokens, ALICE),
        files={"file": ("politika.docx", content, "application/octet-stream")},
        data={"kind": "pd_policy"},
    )
    document_id = created.json()["documentId"]
    await run_jobs(container)
    report = await api.get(
        f"{BASE}/documents/{document_id}/versions/1/checks/latest", headers=auth(tokens, ALICE)
    )
    return document_id, report.json()


async def test_parsed_document_is_checked_with_grounded_findings(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> None:
    _, report = await checked_policy(api, container, tokens)
    run = report["run"]
    assert (run["status"], run["done"]) == ("completed", run["total"])
    statuses = {result["checkCode"]: result["status"] for result in report["results"]}
    assert len(statuses) == run["total"]
    assert statuses["personal_data.purposes"] == "passed"
    assert statuses["personal_data.cross_border"] == "violation"
    assert statuses["personal_data.subject_rights"] == "needs_review"
    assert statuses["formatting.page_margins"] == "passed"

    by_check = {finding["checkCode"]: finding for finding in report["findings"]}
    absent = by_check["personal_data.cross_border"]
    assert absent["location"] is None, "a missing element concerns the whole document"
    assert absent["norm"]["citation"].endswith("ст. 12 152-ФЗ")
    assert "Трансграничная передача" in absent["norm"]["quote"], "quoted from the corpus"
    partial = by_check["personal_data.destruction"]
    assert partial["location"] is not None, "a partial finding points at what is there"
    assert partial["kind"] == "violation"
    assert by_check["personal_data.subject_rights"]["kind"] == "review"


async def test_review_follows_roles_and_revisions_and_survives_a_recheck(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> None:
    document_id, report = await checked_policy(api, container, tokens)
    finding = next(f for f in report["findings"] if f["checkCode"] == "personal_data.cross_border")
    url = f"{BASE}/findings/{finding['id']}"

    def body(review: str, revision: int) -> dict[str, object]:
        return {"review": review, "revision": revision}

    observer = await api.patch(url, json=body("rejected", 0), headers=auth(tokens, OLGA))
    executor = await api.patch(url, json=body("rejected", 0), headers=auth(tokens, EVA))
    assert (observer.status_code, executor.status_code) == (403, 403)
    rejected = await api.patch(url, json=body("rejected", 0), headers=auth(tokens, ALICE))
    assert rejected.json()["review"] == "rejected"
    stale = await api.patch(url, json=body("accepted", 0), headers=auth(tokens, ALICE))
    assert stale.status_code == 409

    rerun = await api.post(
        f"{BASE}/documents/{document_id}/versions/1/checks", headers=auth(tokens, EVA)
    )
    assert rerun.status_code == 202
    await run_jobs(container)
    again = (
        await api.get(
            f"{BASE}/documents/{document_id}/versions/1/checks/latest",
            headers=auth(tokens, ALICE),
        )
    ).json()
    assert again["run"]["id"] == rerun.json()["id"]
    carried = next(f for f in again["findings"] if f["checkCode"] == "personal_data.cross_border")
    assert carried["review"] == "rejected", "a rejected false positive stays rejected"


async def test_runs_and_findings_are_isolated_between_tenants(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> None:
    _, report = await checked_policy(api, container, tokens)
    other = f"/api/v1/organizations/{ORG_B.alias}"
    run = await api.get(f"{other}/check-runs/{report['run']['id']}", headers=auth(tokens, BOB))
    finding = report["findings"][0]
    review = await api.patch(
        f"{other}/findings/{finding['id']}",
        json={"review": "accepted", "revision": 0},
        headers=auth(tokens, BOB),
    )
    assert (run.status_code, review.status_code) == (404, 404)


async def test_progress_stream_reports_the_run_until_it_is_settled(
    api: httpx.AsyncClient, container: Container, tokens: TokenFactory
) -> None:
    _, report = await checked_policy(api, container, tokens)
    async with api.stream(
        "GET", f"{BASE}/check-runs/{report['run']['id']}/events", headers=auth(tokens, OLGA)
    ) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [line async for line in response.aiter_lines() if line.startswith("data:")]
    first = json.loads(events[0].removeprefix("data: "))
    assert first["status"] == "completed"
    assert events[-1] == "data: {}", "the stream ends once the run is settled"


async def test_catalogue_lists_every_check_with_what_it_cites(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    catalog = (await api.get("/api/v1/checks/catalog", headers=auth(tokens, ALICE))).json()
    assert {family["code"] for family in catalog["families"]} == {"formatting", "personal_data"}
    assert all(check["citations"] for check in catalog["checks"])


async def test_quality_of_the_checks_is_published_from_the_last_benchmark(
    api: httpx.AsyncClient, tokens: TokenFactory, settings: Settings
) -> None:
    published = json.loads(settings.checks.quality_report.read_text("utf-8"))
    quality = (await api.get("/api/v1/checks/quality", headers=auth(tokens, ALICE))).json()
    methods = {group["code"]: group["metrics"] for group in quality["methods"]}
    assert methods["deterministic"]["recall"] == 1.0
    assert quality["model"] == published["model"]
    assert quality["current"] is True
    [typical] = [item for item in quality["documents"] if item["typical"]]
    assert typical["pages"] >= 8
    # The model's time is shown only when the model part ran.
    measured = {item["file"]: item["model_ms"] for item in published["documents"]}
    assert typical["modelMs"] == measured[typical["fileName"]]


async def test_without_a_model_api_model_checks_say_so_and_rules_still_run(
    settings: Settings, tokens: TokenFactory
) -> None:
    unconfigured = await build_container(
        settings,
        overrides=Overrides(
            key_source=StaticKeys(tokens),
            directory=FakeDirectory([ORG_A, ORG_B]),
            embedder=HashEmbedder(TEST_SPACE),
        ),
    )
    app = create_app(settings)
    app.state.container = unconfigured
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as api:
            _, report = await checked_policy(api, unconfigured, tokens)
            listed = await api.get(f"{BASE}/workspaces/main/documents", headers=auth(tokens, ALICE))
    finally:
        await unconfigured.close()
    errors = {r["errorCode"] for r in report["results"] if r["method"] == "model"}
    rules = {r["status"] for r in report["results"] if r["method"] == "deterministic"}
    assert errors == {"model_not_configured"}
    assert "error" not in rules
    # The list does not call the document clean: the model checks did not run.
    [summary] = [item["check"] for item in listed.json()["items"]]
    assert summary["notPerformed"] == len([r for r in report["results"] if r["status"] == "error"])
    assert summary["notPerformed"] > 0
