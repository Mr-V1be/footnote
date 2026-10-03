from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from snoska.application.audit.trail import AuditTrail
from snoska.application.billing.meter import UsageMeter
from snoska.domain.audit.event import AuditAction, AuditTarget
from snoska.domain.billing.plans import Plan, PlanCatalog, UsageMetric
from snoska.domain.billing.subscription import Invoice, InvoiceStatus, Subscription
from snoska.domain.billing.usage import LedgerEntry
from snoska.domain.shared.errors import NotFoundError
from snoska.domain.shared.ids import new_id
from snoska.domain.tenancy.access import Actor, ActorKind, OrganizationAccess
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.billing.payments import (
    PaymentProvider,
    PaymentRequest,
    PaymentStatus,
)
from snoska.ports.clock import Clock
from snoska.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

LEDGER_PAGE = 30
INVOICE_PAGE = 24
PAYMENT_ACTOR = Actor(kind=ActorKind.SYSTEM, id=None, label="Платёжный сервис")


class InvoiceNotFoundError(NotFoundError):
    code = "invoice_not_found"


@dataclass(frozen=True, slots=True)
class BillingOverview:
    subscription: Subscription
    plan: Plan
    pending: Plan | None
    used: Mapping[UsageMetric, int]
    members: int | None
    ledger: Sequence[LedgerEntry]
    invoices: Sequence[Invoice]
    plans: Sequence[Plan]
    currency: str


class PlanChange(StrEnum):
    UNCHANGED = "unchanged"
    SCHEDULED = "scheduled"
    AWAITING_PAYMENT = "awaiting_payment"


@dataclass(frozen=True, slots=True)
class PlanChangeOutcome:
    change: PlanChange
    subscription: Subscription
    invoice: Invoice | None = None


class NotificationOutcome(StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"


def _invoice_target(invoice: Invoice) -> AuditTarget:
    return AuditTarget(type="invoice", id=str(invoice.id), label=invoice.number)


class BillingService:
    """Plans, usage and invoices of an organization, and payments for them."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        plans: PlanCatalog,
        meter: UsageMeter,
        provider: PaymentProvider,
        audit: AuditTrail,
        clock: Clock,
        *,
        web_url: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._plans = plans
        self._meter = meter
        self._provider = provider
        self._audit = audit
        self._clock = clock
        self._web_url = web_url.rstrip("/")

    async def overview(
        self, access: OrganizationAccess, members: int | None = None
    ) -> BillingOverview:
        access.require(Permission.BILLING_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            subscription = await self._meter.subscription(uow, access.organization_id, lock=True)
            used = await uow.ledger.totals(subscription.period_start)
            ledger = await uow.ledger.recent(limit=LEDGER_PAGE)
            invoices = await uow.invoices.list(limit=INVOICE_PAGE)
            await uow.commit()
        pending = subscription.pending_plan_code
        return BillingOverview(
            subscription=subscription,
            plan=self._plans.get(subscription.plan_code),
            pending=self._plans.get(pending) if pending else None,
            used=used,
            members=members,
            ledger=ledger,
            invoices=invoices,
            plans=self._plans.all(),
            currency=self._plans.currency,
        )

    async def change_plan(self, access: OrganizationAccess, plan_code: str) -> PlanChangeOutcome:
        """A cheaper plan starts next month; a pricier one once its invoice is paid."""
        access.require(Permission.BILLING_MANAGE)
        target = self._plans.get(plan_code)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            subscription = await self._meter.subscription(uow, access.organization_id, lock=True)
            current = self._plans.get(subscription.plan_code)
            if target.code == current.code or target.rank < current.rank:
                subscription.schedule(target.code)
                await uow.subscriptions.save(subscription)
                change = (
                    PlanChange.UNCHANGED if target.code == current.code else PlanChange.SCHEDULED
                )
                if change is PlanChange.SCHEDULED:
                    await self._audit.record(
                        uow,
                        access,
                        AuditAction.PLAN_CHANGE_REQUESTED,
                        AuditTarget(type="plan", id=target.code, label=target.code),
                        {"from": current.code, "to": target.code, "from_month": "next"},
                    )
                await uow.commit()
                return PlanChangeOutcome(change=change, subscription=subscription)
            invoice = await uow.invoices.open_for_plan(target.code)
            if invoice is None:
                invoice = await self._issue(uow, access, target, subscription)
            await uow.commit()
        return PlanChangeOutcome(
            change=PlanChange.AWAITING_PAYMENT, subscription=subscription, invoice=invoice
        )

    async def _issue(
        self,
        uow: UnitOfWork,
        access: OrganizationAccess,
        target: Plan,
        subscription: Subscription,
    ) -> Invoice:
        now = self._clock.now()
        invoice = Invoice(
            id=new_id(),
            organization_id=access.organization_id,
            number=await uow.invoices.next_number(now.year),
            plan_code=target.code,
            amount_kopecks=target.price_kopecks,
            period_start=subscription.period_start,
            status=InvoiceStatus.OPEN,
            issued_at=now,
        )
        session = await self._provider.open_payment(
            PaymentRequest(
                invoice_id=invoice.id,
                organization_id=access.organization_id,
                amount_kopecks=invoice.amount_kopecks,
                currency=self._plans.currency,
                description=f"{invoice.number}: {target.code}",
                return_url=f"{self._web_url}/o/{access.organization.alias}/billing",
            )
        )
        invoice.payment_id, invoice.payment_url = session.payment_id, session.confirmation_url
        await uow.invoices.add(invoice)
        await self._audit.record(
            uow,
            access,
            AuditAction.PLAN_CHANGE_REQUESTED,
            _invoice_target(invoice),
            {"to": target.code, "amount_kopecks": invoice.amount_kopecks},
        )
        return invoice

    async def handle_notification(
        self, provider: str, body: bytes, headers: dict[str, str]
    ) -> NotificationOutcome:
        """A payment provider's webhook: idempotent by the provider's event id."""
        if provider != self._provider.name:
            raise InvoiceNotFoundError(f"unknown payment provider {provider!r}")
        notice = self._provider.parse_notification(body, headers)
        now = self._clock.now()
        async with self._uow_factory.for_tenant(notice.organization_id) as uow:
            if not await uow.payment_events.first_time(
                provider, notice.event_id, notice.invoice_id, now
            ):
                return NotificationOutcome.DUPLICATE
            invoice = await uow.invoices.get(notice.invoice_id)
            if invoice is None or invoice.payment_id != notice.payment_id:
                raise InvoiceNotFoundError("the payment does not match an invoice")
            if notice.status is PaymentStatus.SUCCEEDED and invoice.pay(now):
                await uow.invoices.save(invoice)
                subscription = await self._meter.subscription(
                    uow, notice.organization_id, lock=True
                )
                previous = subscription.plan_code
                subscription.switch(invoice.plan_code)
                await uow.subscriptions.save(subscription)
                await self._audit.record_as(
                    uow,
                    notice.organization_id,
                    PAYMENT_ACTOR,
                    AuditAction.INVOICE_PAID,
                    _invoice_target(invoice),
                    {"amount_kopecks": invoice.amount_kopecks},
                )
                await self._audit.record_as(
                    uow,
                    notice.organization_id,
                    PAYMENT_ACTOR,
                    AuditAction.PLAN_CHANGED,
                    AuditTarget(type="plan", id=invoice.plan_code, label=invoice.plan_code),
                    {"from": previous, "to": invoice.plan_code},
                )
            await uow.commit()
        return NotificationOutcome.PROCESSED

    async def assign(self, organization_id: UUID, plan_code: str, actor: Actor) -> Subscription:
        """The platform's operator moves an organization to a plan at once."""
        plan = self._plans.get(plan_code)
        async with self._uow_factory.for_tenant(organization_id) as uow:
            subscription = await self._meter.subscription(uow, organization_id, lock=True)
            previous = subscription.plan_code
            subscription.switch(plan.code)
            await uow.subscriptions.save(subscription)
            await self._audit.record_as(
                uow,
                organization_id,
                actor,
                AuditAction.PLAN_CHANGED,
                AuditTarget(type="plan", id=plan.code, label=plan.code),
                {"from": previous, "to": plan.code},
            )
            await uow.commit()
        return subscription

    async def usage_of(
        self, organization_id: UUID
    ) -> tuple[Subscription, Mapping[UsageMetric, int]]:
        """For the platform's operator: an organization's plan and month."""
        async with self._uow_factory.for_tenant(organization_id) as uow:
            subscription = await self._meter.subscription(uow, organization_id, lock=True)
            used = await uow.ledger.totals(subscription.period_start)
            await uow.commit()
        return subscription, used

    @property
    def plans(self) -> PlanCatalog:
        return self._plans
