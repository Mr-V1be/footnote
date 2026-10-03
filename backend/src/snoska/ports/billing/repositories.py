from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from snoska.domain.billing.plans import UsageMetric
from snoska.domain.billing.subscription import Invoice, Subscription
from snoska.domain.billing.usage import LedgerEntry


class SubscriptionRepository(Protocol):
    """Tenant-scoped; one subscription per organization."""

    async def get(self) -> Subscription | None: ...

    async def lock(self) -> Subscription | None:
        """Load and lock it: usage checks of one organization run one at a time."""
        ...

    async def add(self, subscription: Subscription) -> None: ...

    async def save(self, subscription: Subscription) -> None: ...


class LedgerRepository(Protocol):
    """Tenant-scoped, append-only."""

    async def add(self, entry: LedgerEntry) -> None: ...

    async def totals(self, period_start: date) -> Mapping[UsageMetric, int]: ...

    async def recent(self, *, limit: int) -> Sequence[LedgerEntry]: ...


class InvoiceRepository(Protocol):
    """Tenant-scoped, except finding an invoice by its payment."""

    async def add(self, invoice: Invoice) -> None: ...

    async def save(self, invoice: Invoice) -> None: ...

    async def get(self, invoice_id: UUID) -> Invoice | None: ...

    async def list(self, *, limit: int) -> Sequence[Invoice]: ...

    async def open_for_plan(self, plan_code: str) -> Invoice | None: ...

    async def next_number(self, year: int) -> str: ...


class PaymentEventLog(Protocol):
    """Notifications already handled, by the provider's event id (tenant-scoped)."""

    async def first_time(
        self, provider: str, event_id: str, invoice_id: UUID, now: datetime
    ) -> bool:
        """Record the event; False when it was recorded before."""
        ...
