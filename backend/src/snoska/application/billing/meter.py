from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from snoska.domain.billing.plans import Plan, PlanCatalog, UsageMetric
from snoska.domain.billing.subscription import Subscription, month_start
from snoska.domain.billing.usage import LedgerEntry, LedgerReason, ensure_allowance
from snoska.domain.shared.ids import new_id
from snoska.ports.clock import Clock
from snoska.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class Charge:
    metric: UsageMetric
    quantity: int


class UsageMeter:
    """Counts usage against the plan, inside the caller's transaction.

    The organization's subscription row is locked first, so two requests of
    one organization cannot both pass the last unit of a limit: the second
    waits and then sees the first one's entry.
    """

    def __init__(self, plans: PlanCatalog, clock: Clock) -> None:
        self._plans = plans
        self._clock = clock

    async def subscription(
        self, uow: UnitOfWork, organization_id: UUID, *, lock: bool
    ) -> Subscription:
        """The organization's subscription in the current month (created on first use)."""
        found = await (uow.subscriptions.lock() if lock else uow.subscriptions.get())
        if found is None:
            await uow.subscriptions.add(
                Subscription(
                    organization_id=organization_id,
                    plan_code=self._plans.default.code,
                    period_start=month_start(self._clock.now().date()),
                )
            )
            found = await uow.subscriptions.lock()
            if found is None:
                raise RuntimeError("subscription could not be created")
        if found.roll(self._clock.now().date()):
            await uow.subscriptions.save(found)
        return found

    def plan_of(self, subscription: Subscription) -> Plan:
        return self._plans.get(subscription.plan_code)

    async def consume(
        self,
        uow: UnitOfWork,
        organization_id: UUID,
        charges: Sequence[Charge],
        reason: LedgerReason,
        reference: str,
    ) -> None:
        """Book the charges, or raise QuotaExceededError and book nothing."""
        subscription = await self.subscription(uow, organization_id, lock=True)
        plan = self.plan_of(subscription)
        totals = await uow.ledger.totals(subscription.period_start)
        for charge in charges:
            ensure_allowance(plan, charge.metric, totals.get(charge.metric, 0), charge.quantity)
        now = self._clock.now()
        for charge in charges:
            await uow.ledger.add(
                LedgerEntry(
                    id=new_id(),
                    organization_id=organization_id,
                    metric=charge.metric,
                    quantity=charge.quantity,
                    reason=reason,
                    reference=reference,
                    period_start=subscription.period_start,
                    created_at=now,
                )
            )

    async def ensure_members(self, uow: UnitOfWork, organization_id: UUID, current: int) -> None:
        """One more member fits the plan."""
        subscription = await self.subscription(uow, organization_id, lock=False)
        ensure_allowance(self.plan_of(subscription), UsageMetric.MEMBERS, current, 1)
