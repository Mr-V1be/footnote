"""API keys and webhooks: integrations acting for an organization."""

from __future__ import annotations

import json

import httpx
from sqlalchemy import text

from snoska.bootstrap.container import Container
from snoska.domain.integrations.webhooks import verify_signature
from tests.integration.test_administration import DEMO, upload
from tests.support.fakes import RecordingTransport
from tests.support.scenario import ALICE, EVA, auth, run_jobs
from tests.support.tokens import TokenFactory

BASE = "/api/v1/organizations/alpha"


def key_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_an_api_key_acts_within_its_scopes_until_revoked(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    created = await api.post(
        f"{BASE}/api-keys",
        headers=auth(tokens, ALICE),
        json={"name": "CRM", "scopes": ["documents:read"]},
    )
    assert created.status_code == 201, created.text
    token, key = created.json()["token"], created.json()["key"]
    assert token.startswith("snk_")
    assert token[4:].startswith(key["prefix"])

    listed = await api.get(f"{BASE}/api-keys", headers=auth(tokens, ALICE))
    assert "token" not in listed.json()[0]
    assert (await api.get(f"{BASE}/api-keys", headers=auth(tokens, EVA))).status_code == 403

    documents = await api.get(f"{BASE}/workspaces/main/documents", headers=key_auth(token))
    assert documents.status_code == 200
    refused = await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=key_auth(token),
        files={"file": ("x.docx", b"PK\x03\x04", "application/octet-stream")},
    )
    assert refused.status_code == 403
    # A key belongs to one organization.
    other = await api.get(
        "/api/v1/organizations/beta/workspaces/main/documents", headers=key_auth(token)
    )
    assert other.status_code == 401

    await api.delete(f"{BASE}/api-keys/{key['id']}", headers=auth(tokens, ALICE))
    revoked = await api.get(f"{BASE}/workspaces/main/documents", headers=key_auth(token))
    assert revoked.status_code == 401
    log = await api.get(f"{BASE}/audit", headers=auth(tokens, ALICE))
    assert [item["action"] for item in log.json()["items"]] == [
        "api_key.revoked",
        "api_key.created",
    ]


async def test_an_upload_with_a_key_is_named_after_the_key(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    created = await api.post(
        f"{BASE}/api-keys",
        headers=auth(tokens, ALICE),
        json={"name": "Робот загрузки", "scopes": ["documents:write"]},
    )
    token = created.json()["token"]
    content = DEMO / "soglasie-pokupatelya.docx"
    uploaded = await api.post(
        f"{BASE}/workspaces/main/documents",
        headers=key_auth(token),
        files={"file": ("s.docx", await content.read_bytes(), "application/octet-stream")},
    )
    assert uploaded.status_code == 201, uploaded.text
    log = await api.get(f"{BASE}/audit", headers=auth(tokens, ALICE))
    entry = log.json()["items"][0]
    assert (entry["action"], entry["actor"]["kind"]) == ("document.uploaded", "api_key")
    assert entry["actor"]["label"].startswith("Робот загрузки")


async def test_events_are_signed_delivered_and_retried_with_backoff(
    api: httpx.AsyncClient,
    tokens: TokenFactory,
    container: Container,
    receiver: RecordingTransport,
) -> None:
    created = await api.post(
        f"{BASE}/webhooks",
        headers=auth(tokens, ALICE),
        json={
            "url": "https://hooks.alpha.example/snoska",
            "events": ["document.uploaded", "check.completed"],
        },
    )
    assert created.status_code == 201, created.text
    secret, endpoint = created.json()["secret"], created.json()["endpoint"]
    assert "secret" not in (await api.get(f"{BASE}/webhooks", headers=auth(tokens, ALICE))).text

    await upload(api, tokens, "main")
    await run_jobs(container)
    events = [headers["Snoska-Event"] for _, _, headers in receiver.sent]
    assert events == ["document.uploaded", "check.completed"]
    _, body, headers = receiver.sent[0]
    assert verify_signature(secret, headers["Snoska-Signature"], body)
    assert not verify_signature("whsec_other", headers["Snoska-Signature"], body)
    assert json.loads(body)["data"]["kind"] == "pd_consent"

    deliveries = await api.get(
        f"{BASE}/webhooks/{endpoint['id']}/deliveries", headers=auth(tokens, ALICE)
    )
    assert {item["status"] for item in deliveries.json()} == {"delivered"}

    # The receiver fails: the delivery waits for its next try instead of looping.
    receiver.respond_with(500)
    pinged = await api.post(f"{BASE}/webhooks/{endpoint['id']}/ping", headers=auth(tokens, ALICE))
    assert pinged.status_code == 202
    await run_jobs(container)
    latest = (
        await api.get(f"{BASE}/webhooks/{endpoint['id']}/deliveries", headers=auth(tokens, ALICE))
    ).json()[0]
    assert (latest["event"], latest["status"], latest["attempts"]) == ("ping", "retrying", 1)
    assert latest["lastStatusCode"] == 500
    assert latest["nextAttemptAt"] is not None
    async with container.engine.begin() as connection:
        waiting = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM outbox_messages "
                    "WHERE dispatched_at IS NULL AND available_at > now()"
                )
            )
        ).scalar_one()
    assert waiting == 1
    busy = await api.post(
        f"{BASE}/webhooks/{endpoint['id']}/deliveries/{latest['id']}/retry",
        headers=auth(tokens, ALICE),
    )
    assert busy.status_code == 409


async def test_webhook_urls_must_be_https_outside_the_demo_stand(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    refused = await api.post(
        f"{BASE}/webhooks",
        headers=auth(tokens, ALICE),
        json={"url": "ftp://hooks.example", "events": ["check.completed"]},
    )
    assert refused.status_code == 422
