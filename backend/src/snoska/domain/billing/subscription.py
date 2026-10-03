from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from snoska.domain.shared.errors import InvalidStateError


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month(day: date) -> date:
    return date(day.year + day.month // 12, day.month % 12 + 1, 1)


@dataclass(slots=True)
class Subscription:
    """An organization's plan and its current billing month.

    Months run from the first day; a move to a cheaper plan waits for the
    next month, a paid upgrade applies when its invoice is paid.
    """

    organization_id: UUID
    plan_code: str
    period_start: date
    pending_plan_code: str | None = None
    revision: int = 0

    @property
    def period_end(self) -> date:
        return next_month(self.period_start)

    def roll(self, today: date) -> bool:
        """Move to the month containing ``today``; True when it moved."""
        current = month_start(today)
        if current <= self.period_start:
            return False
        self.period_start = current
        if self.pending_plan_code is not None:
            self.plan_code, self.pending_plan_code = self.pending_plan_code, None
        return True

    def switch(self, plan_code: str) -> None:
        self.plan_code, self.pending_plan_code = plan_code, None

    def schedule(self, plan_code: str) -> None:
        self.pending_plan_code = None if plan_code == self.plan_code else plan_code


class InvoiceStatus(StrEnum):
    OPEN = "open"
    PAID = "paid"
    VOID = "void"


class InvoiceNotPayableError(InvalidStateError):
    code = "invoice_not_payable"


@dataclass(slots=True)
class Invoice:
    """A bill for a plan's month. Paid through the payment provider."""

    id: UUID
    organization_id: UUID
    number: str
    plan_code: str
    amount_kopecks: int
    period_start: date
    status: InvoiceStatus
    issued_at: datetime
    payment_id: str | None = None
    payment_url: str | None = None
    paid_at: datetime | None = None

    def pay(self, now: datetime) -> bool:
        """Mark paid; False when it already was (a repeated notification)."""
        if self.status is InvoiceStatus.PAID:
            return False
        if self.status is InvoiceStatus.VOID:
            raise InvoiceNotPayableError("the invoice was cancelled")
        self.status, self.paid_at = InvoiceStatus.PAID, now
        return True

    def void(self) -> None:
        if self.status is InvoiceStatus.OPEN:
            self.status = InvoiceStatus.VOID
