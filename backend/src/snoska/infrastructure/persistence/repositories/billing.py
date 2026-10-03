from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.billing.plans import UsageMetric
from snoska.domain.billing.subscription import Invoice, InvoiceStatus, Subscription
from snoska.domain.billing.usage import LedgerEntry, LedgerReason
from snoska.infrastructure.persistence.tables.billing import (
    INVOICE_NUMBERS,
    invoices,
    payment_events,
    subscriptions,
    usage_ledger,
)

INVOICE_PREFIX = "СН"


def _subscription(row: RowMapping) -> Subscription:
    return Subscription(
        organization_id=row["organization_id"],
        plan_code=row["plan_code"],
        period_start=row["period_start"],
        pending_plan_code=row["pending_plan_code"],
        revision=row["revision"],
    )


class SqlSubscriptionRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get(self) -> Subscription | None:
        row = (await self._connection.execute(select(subscriptions))).mappings().first()
        return _subscription(row) if row else None

    async def lock(self) -> Subscription | None:
        row = (
            (await self._connection.execute(select(subscriptions).with_for_update()))
            .mappings()
            .first()
        )
        return _subscription(row) if row else None

    async def add(self, subscription: Subscription) -> None:
        await self._connection.execute(
            pg_insert(subscriptions)
            .values(
                organization_id=subscription.organization_id,
                plan_code=subscription.plan_code,
                period_start=subscription.period_start,
                pending_plan_code=subscription.pending_plan_code,
                revision=0,
            )
            .on_conflict_do_nothing(index_elements=[subscriptions.c.organization_id])
        )

    async def save(self, subscription: Subscription) -> None:
        await self._connection.execute(
            update(subscriptions)
            .where(subscriptions.c.organization_id == subscription.organization_id)
            .values(
                plan_code=subscription.plan_code,
                period_start=subscription.period_start,
                pending_plan_code=subscription.pending_plan_code,
                revision=subscriptions.c.revision + 1,
            )
        )


def _entry(row: RowMapping) -> LedgerEntry:
    return LedgerEntry(
        id=row["id"],
        organization_id=row["organization_id"],
        metric=UsageMetric(row["metric"]),
        quantity=row["quantity"],
        reason=LedgerReason(row["reason"]),
        reference=row["reference"],
        period_start=row["period_start"],
        created_at=row["created_at"],
    )


class SqlLedgerRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, entry: LedgerEntry) -> None:
        await self._connection.execute(
            insert(usage_ledger).values(
                id=entry.id,
                organization_id=entry.organization_id,
                metric=entry.metric.value,
                quantity=entry.quantity,
                reason=entry.reason.value,
                reference=entry.reference,
                period_start=entry.period_start,
                created_at=entry.created_at,
            )
        )

    async def totals(self, period_start: date) -> Mapping[UsageMetric, int]:
        result = await self._connection.execute(
            select(usage_ledger.c.metric, func.sum(usage_ledger.c.quantity))
            .where(usage_ledger.c.period_start == period_start)
            .group_by(usage_ledger.c.metric)
        )
        return {UsageMetric(metric): int(total) for metric, total in result}

    async def recent(self, *, limit: int) -> Sequence[LedgerEntry]:
        result = await self._connection.execute(
            select(usage_ledger)
            .order_by(usage_ledger.c.created_at.desc(), usage_ledger.c.id)
            .limit(limit)
        )
        return [_entry(row) for row in result.mappings()]


def _invoice(row: RowMapping) -> Invoice:
    return Invoice(
        id=row["id"],
        organization_id=row["organization_id"],
        number=row["number"],
        plan_code=row["plan_code"],
        amount_kopecks=row["amount_kopecks"],
        period_start=row["period_start"],
        status=InvoiceStatus(row["status"]),
        issued_at=row["issued_at"],
        payment_id=row["payment_id"],
        payment_url=row["payment_url"],
        paid_at=row["paid_at"],
    )


class SqlInvoiceRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    @staticmethod
    def _state(invoice: Invoice) -> dict[str, Any]:
        return {
            "status": invoice.status.value,
            "payment_id": invoice.payment_id,
            "payment_url": invoice.payment_url,
            "paid_at": invoice.paid_at,
        }

    async def add(self, invoice: Invoice) -> None:
        await self._connection.execute(
            insert(invoices).values(
                id=invoice.id,
                organization_id=invoice.organization_id,
                number=invoice.number,
                plan_code=invoice.plan_code,
                amount_kopecks=invoice.amount_kopecks,
                period_start=invoice.period_start,
                issued_at=invoice.issued_at,
                **self._state(invoice),
            )
        )

    async def save(self, invoice: Invoice) -> None:
        await self._connection.execute(
            update(invoices).where(invoices.c.id == invoice.id).values(**self._state(invoice))
        )

    async def get(self, invoice_id: UUID) -> Invoice | None:
        row = (
            (await self._connection.execute(select(invoices).where(invoices.c.id == invoice_id)))
            .mappings()
            .first()
        )
        return _invoice(row) if row else None

    async def list(self, *, limit: int) -> Sequence[Invoice]:
        result = await self._connection.execute(
            select(invoices).order_by(invoices.c.issued_at.desc()).limit(limit)
        )
        return [_invoice(row) for row in result.mappings()]

    async def open_for_plan(self, plan_code: str) -> Invoice | None:
        row = (
            (
                await self._connection.execute(
                    select(invoices).where(
                        invoices.c.plan_code == plan_code,
                        invoices.c.status == InvoiceStatus.OPEN.value,
                    )
                )
            )
            .mappings()
            .first()
        )
        return _invoice(row) if row else None

    async def next_number(self, year: int) -> str:
        value = (await self._connection.execute(select(INVOICE_NUMBERS.next_value()))).scalar_one()
        return f"{INVOICE_PREFIX}-{year}-{int(value):06d}"


class SqlPaymentEventLog:
    def __init__(self, connection: AsyncConnection, organization_id: UUID | None) -> None:
        self._connection = connection
        self._organization_id = organization_id

    async def first_time(
        self, provider: str, event_id: str, invoice_id: UUID, now: datetime
    ) -> bool:
        if self._organization_id is None:
            raise RuntimeError("payment events are recorded in a tenant unit of work")
        result = await self._connection.execute(
            pg_insert(payment_events)
            .values(
                organization_id=self._organization_id,
                provider=provider,
                event_id=event_id,
                invoice_id=invoice_id,
                received_at=now,
            )
            .on_conflict_do_nothing(index_elements=["provider", "event_id"])
            .returning(payment_events.c.event_id)
        )
        return result.first() is not None
