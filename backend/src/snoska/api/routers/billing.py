from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from snoska.api.cursors import decode_time_cursor, encode_time_cursor
from snoska.api.dependencies import ContainerDep, OrganizationAccessDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.schemas.billing.billing import (
    BillingOut,
    LedgerEntryOut,
    LedgerPageOut,
    PlanChangeIn,
    PlanChangeOut,
    TestDecisionIn,
    TestDecisionOut,
    TestPaymentOut,
)
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.billing.payments import PaymentStatus

router = APIRouter(prefix="/v1", tags=["billing"], responses=PROBLEM_RESPONSES)


@router.get(
    "/organizations/{organization}/billing", response_model=BillingOut, response_model_by_alias=True
)
async def billing_overview(container: ContainerDep, access: OrganizationAccessDep) -> BillingOut:
    """Plan, this month's usage against its limits, the ledger and invoices."""
    members = None
    if access.can(Permission.MEMBERS_MANAGE):
        members = len(await container.members.list(access))
    return BillingOut.of(await container.billing.overview(access, members))


@router.get(
    "/organizations/{organization}/billing/ledger",
    response_model=LedgerPageOut,
    response_model_by_alias=True,
)
async def billing_ledger(
    container: ContainerDep,
    access: OrganizationAccessDep,
    cursor: str | None = None,
    limit: int | None = None,
) -> LedgerPageOut:
    """This month's charges, each with its reason, newest first."""
    page = await container.billing.ledger(
        access, decode_time_cursor(cursor) if cursor else None, limit
    )
    return LedgerPageOut(
        items=[LedgerEntryOut.of(entry) for entry in page.items],
        next_cursor=encode_time_cursor(page.next_cursor) if page.next_cursor else None,
    )


@router.post(
    "/organizations/{organization}/billing/plan",
    response_model=PlanChangeOut,
    response_model_by_alias=True,
)
async def change_plan(
    container: ContainerDep, access: OrganizationAccessDep, body: PlanChangeIn
) -> PlanChangeOut:
    """A cheaper plan from next month; a pricier one after paying its invoice."""
    return PlanChangeOut.of(await container.billing.change_plan(access, body.plan))


@router.post("/billing/webhooks/{provider}", include_in_schema=False)
async def payment_webhook(
    provider: str, request: Request, container: ContainerDep
) -> dict[str, str]:
    """Notifications of the payment provider; repeated ones are acknowledged."""
    outcome = await container.billing.handle_notification(
        provider, await request.body(), dict(request.headers)
    )
    return {"status": outcome.value}


# ── The test provider's own side: its checkout and decision ─────────────────


@router.get(
    "/test-payments/{payment_id}", response_model=TestPaymentOut, response_model_by_alias=True
)
async def test_payment(
    payment_id: str, container: ContainerDep, token: Annotated[str, Query(max_length=4000)]
) -> TestPaymentOut:
    """What the test checkout shows (no session: the signed token is the access)."""
    payment = container.test_gateway.checkout(payment_id, token)
    return TestPaymentOut(
        payment_id=payment.payment_id,
        amount_kopecks=payment.amount_kopecks,
        currency=payment.currency,
        description=payment.description,
    )


@router.post(
    "/test-payments/{payment_id}/decision",
    response_model=TestDecisionOut,
    response_model_by_alias=True,
)
async def decide_test_payment(
    payment_id: str, container: ContainerDep, body: TestDecisionIn
) -> TestDecisionOut:
    status = PaymentStatus.SUCCEEDED if body.succeeded else PaymentStatus.CANCELED
    decision = await container.test_gateway.decide(payment_id, body.token, status)
    return TestDecisionOut(return_url=decision.return_url)
