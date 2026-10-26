from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from footnote.api.schemas.common import ApiModel
from footnote.application.billing.service import BillingOverview, PlanChange, PlanChangeOutcome
from footnote.domain.billing.plans import METERED, Plan, UsageMetric
from footnote.domain.billing.subscription import Invoice, InvoiceStatus
from footnote.domain.billing.usage import LedgerEntry, LedgerReason


class PlanOut(ApiModel):
    code: str
    rank: int
    price_kopecks: int
    limits: dict[UsageMetric, int]

    @classmethod
    def of(cls, plan: Plan) -> PlanOut:
        return cls(
            code=plan.code,
            rank=plan.rank,
            price_kopecks=plan.price_kopecks,
            limits=dict(plan.limits),
        )


class UsageOut(ApiModel):
    metric: UsageMetric
    used: int | None
    limit: int


class LedgerEntryOut(ApiModel):
    id: UUID
    metric: UsageMetric
    quantity: int
    reason: LedgerReason
    reference: str
    created_at: datetime

    @classmethod
    def of(cls, entry: LedgerEntry) -> LedgerEntryOut:
        return cls(
            id=entry.id,
            metric=entry.metric,
            quantity=entry.quantity,
            reason=entry.reason,
            reference=entry.reference,
            created_at=entry.created_at,
        )


class PlansOut(ApiModel):
    plans: list[PlanOut]
    currency: str


class LedgerPageOut(ApiModel):
    items: list[LedgerEntryOut]
    next_cursor: str | None


class InvoiceOut(ApiModel):
    id: UUID
    number: str
    plan_code: str
    amount_kopecks: int
    period_start: date
    status: InvoiceStatus
    issued_at: datetime
    paid_at: datetime | None
    # Where to pay while the invoice is open.
    payment_url: str | None

    @classmethod
    def of(cls, invoice: Invoice) -> InvoiceOut:
        return cls(
            id=invoice.id,
            number=invoice.number,
            plan_code=invoice.plan_code,
            amount_kopecks=invoice.amount_kopecks,
            period_start=invoice.period_start,
            status=invoice.status,
            issued_at=invoice.issued_at,
            paid_at=invoice.paid_at,
            payment_url=invoice.payment_url if invoice.status is InvoiceStatus.OPEN else None,
        )


class BillingOut(ApiModel):
    plan: PlanOut
    pending_plan: PlanOut | None
    period_start: date
    period_end: date
    currency: str
    usage: list[UsageOut]
    invoices: list[InvoiceOut]
    plans: list[PlanOut]

    @classmethod
    def of(cls, overview: BillingOverview) -> BillingOut:
        plan = overview.plan
        usage = [
            UsageOut(metric=metric, used=overview.used.get(metric, 0), limit=plan.limit(metric))
            for metric in METERED
        ]
        usage.append(
            UsageOut(
                metric=UsageMetric.MEMBERS,
                used=overview.members,
                limit=plan.limit(UsageMetric.MEMBERS),
            )
        )
        return cls(
            plan=PlanOut.of(plan),
            pending_plan=PlanOut.of(overview.pending) if overview.pending else None,
            period_start=overview.subscription.period_start,
            period_end=overview.subscription.period_end,
            currency=overview.currency,
            usage=usage,
            invoices=[InvoiceOut.of(invoice) for invoice in overview.invoices],
            plans=[PlanOut.of(item) for item in overview.plans],
        )


class PlanChangeIn(ApiModel):
    plan: str = Field(min_length=1, max_length=40)


class PlanChangeOut(ApiModel):
    change: PlanChange
    invoice: InvoiceOut | None

    @classmethod
    def of(cls, outcome: PlanChangeOutcome) -> PlanChangeOut:
        return cls(
            change=outcome.change,
            invoice=InvoiceOut.of(outcome.invoice) if outcome.invoice else None,
        )


class TestPaymentOut(ApiModel):
    __test__ = False

    payment_id: str
    amount_kopecks: int
    currency: str
    description: str


class TestDecisionIn(ApiModel):
    __test__ = False

    token: str = Field(min_length=10, max_length=4000)
    succeeded: bool


class TestDecisionOut(ApiModel):
    __test__ = False

    return_url: str
