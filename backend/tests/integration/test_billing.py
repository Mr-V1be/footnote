"""Plans and limits: usage booked in whole units, limits checked atomically,
invoices paid through the test provider's signed, idempotent notifications."""

from __future__ import annotations

import asyncio

import httpx

from footnote.bootstrap.container import Container
from footnote.domain.tenancy.access import SYSTEM_ACTOR
from footnote.infrastructure.billing.test_provider import TestPaymentProvider
from footnote.ports.billing.payments import PaymentStatus
from tests.integration.test_administration import upload
from tests.support.scenario import ALICE, EVA, LEO, ORG_A, auth, run_jobs
from tests.support.tokens import TokenFactory

BASE = "/api/v1/organizations/alpha"


def usage_of(billing: dict, metric: str) -> int:  # type: ignore[type-arg]
    return next(item["used"] for item in billing["usage"] if item["metric"] == metric)


async def test_a_check_books_its_pages_and_the_limit_stops_the_next(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    first = await upload(api, tokens, "main")
    await run_jobs(container)
    billing = (await api.get(f"{BASE}/billing", headers=auth(tokens, LEO))).json()
    assert billing["plan"]["code"] == "start"
    assert usage_of(billing, "checks") == 1
    assert usage_of(billing, "pages") >= 1
    ledger = (await api.get(f"{BASE}/billing/ledger", headers=auth(tokens, LEO))).json()
    assert {entry["reason"] for entry in ledger["items"]} == {"check_run"}
    assert {entry["metric"] for entry in ledger["items"]} == {"pages", "checks"}
    # A page at a time: the cursor leads to the rest of the month.
    first_page = (
        await api.get(f"{BASE}/billing/ledger", headers=auth(tokens, LEO), params={"limit": 1})
    ).json()
    assert len(first_page["items"]) == 1
    rest = (
        await api.get(
            f"{BASE}/billing/ledger",
            headers=auth(tokens, LEO),
            params={"limit": 1, "cursor": first_page["nextCursor"]},
        )
    ).json()
    assert rest["items"][0]["id"] != first_page["items"][0]["id"]

    # Down to a plan that allows one check a month: the next one is refused.
    await container.billing.assign(ORG_A.id, "tiny", SYSTEM_ACTOR)
    refused = await api.post(
        f"{BASE}/documents/{first}/versions/1/checks", headers=auth(tokens, EVA)
    )
    assert refused.status_code == 402
    assert refused.json()["code"] == "quota_exceeded"

    # An upload past the limit is still parsed; its check says why it did not run.
    second = await upload(api, tokens, "main")
    await run_jobs(container)
    report = await api.get(
        f"{BASE}/documents/{second}/versions/1/checks/latest", headers=auth(tokens, EVA)
    )
    assert report.json()["run"]["status"] == "failed"
    assert report.json()["run"]["failureCode"] == "quota_exceeded"


async def test_concurrent_requests_cannot_both_take_the_last_unit(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    documents = [await upload(api, tokens, "main") for _ in range(2)]
    await run_jobs(container)  # two runs: two of the start plan's three checks
    # Two requests race for the last check of the month.
    results = await asyncio.gather(
        *(
            api.post(f"{BASE}/documents/{document}/versions/1/checks", headers=auth(tokens, EVA))
            for document in documents
        )
    )
    assert sorted(response.status_code for response in results) == [202, 402]
    billing = (await api.get(f"{BASE}/billing", headers=auth(tokens, LEO))).json()
    assert usage_of(billing, "checks") == 3


async def test_an_upgrade_is_paid_through_the_provider_once(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    refused = await api.post(
        f"{BASE}/billing/plan", headers=auth(tokens, LEO), json={"plan": "team"}
    )
    assert refused.status_code == 403
    changed = await api.post(
        f"{BASE}/billing/plan", headers=auth(tokens, ALICE), json={"plan": "team"}
    )
    assert changed.json()["change"] == "awaiting_payment"
    invoice = changed.json()["invoice"]
    assert invoice["amountKopecks"] == 490000
    assert invoice["number"].startswith("СН-")
    assert "/pay/test/" in invoice["paymentUrl"]

    provider = TestPaymentProvider("test-payments", "http://web.test")
    payment_id = invoice["paymentUrl"].split("/pay/test/")[1].split("?")[0]
    token = invoice["paymentUrl"].split("token=")[1]
    shown = await api.get(f"/api/v1/test-payments/{payment_id}", params={"token": token})
    assert shown.json()["amountKopecks"] == 490000
    payment = provider.payment(payment_id, httpx.URL(f"?token={token}").params["token"])
    body, headers = provider.notification(payment, PaymentStatus.SUCCEEDED)

    forged = await api.post(
        "/api/v1/billing/webhooks/test", content=body, headers={"Test-Payments-Signature": "x"}
    )
    assert forged.status_code == 400
    first = await api.post("/api/v1/billing/webhooks/test", content=body, headers=headers)
    again = await api.post("/api/v1/billing/webhooks/test", content=body, headers=headers)
    assert (first.json()["status"], again.json()["status"]) == ("processed", "duplicate")

    billing = (await api.get(f"{BASE}/billing", headers=auth(tokens, ALICE))).json()
    assert billing["plan"]["code"] == "team"
    assert billing["invoices"][0]["status"] == "paid"
    log = (await api.get(f"{BASE}/audit", headers=auth(tokens, ALICE))).json()["items"]
    assert [item["action"] for item in log[:2]] == ["billing.plan_changed", "billing.invoice_paid"]


async def test_a_cheaper_plan_waits_for_the_next_month(
    api: httpx.AsyncClient, tokens: TokenFactory
) -> None:
    changed = await api.post(
        f"{BASE}/billing/plan", headers=auth(tokens, ALICE), json={"plan": "tiny"}
    )
    assert changed.json()["change"] == "scheduled"
    billing = (await api.get(f"{BASE}/billing", headers=auth(tokens, ALICE))).json()
    assert (billing["plan"]["code"], billing["pendingPlan"]["code"]) == ("start", "tiny")


async def test_the_plan_caps_members(
    api: httpx.AsyncClient, tokens: TokenFactory, container: Container
) -> None:
    await container.billing.assign(ORG_A.id, "tiny", SYSTEM_ACTOR)
    refused = await api.post(
        f"{BASE}/members",
        headers=auth(tokens, ALICE),
        json={"email": "x@alpha.example", "firstName": "И", "lastName": "К", "role": "observer"},
    )
    assert refused.status_code == 402
