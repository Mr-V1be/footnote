from __future__ import annotations

import structlog

from snoska.application.checks.scheduling import CheckScheduler
from snoska.ports.ai import RequestBudget
from snoska.ports.jobs import JobPayload
from snoska.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)


class RecheckDocuments:
    """Operations: queue a check of every document's latest version.

    Used after the check catalogue changes, so stored results reflect the
    current rules. Runs already waiting are joined, not duplicated.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, scheduler: CheckScheduler) -> None:
        self._uow_factory = uow_factory
        self._scheduler = scheduler

    async def all_organizations(self) -> dict[str, int]:
        scheduled: dict[str, int] = {}
        offset, page = 0, 100
        while True:
            async with self._uow_factory.for_platform() as uow:
                organizations = await uow.organizations.list_all(limit=page, offset=offset)
            if not organizations:
                return scheduled
            for organization in organizations:
                async with self._uow_factory.for_tenant(organization.id) as uow:
                    versions = await uow.versions.latest_parsed()
                    for version in versions:
                        # Re-checking after a catalogue change is the operator's,
                        # not counted against the organization's plan.
                        await self._scheduler.schedule(
                            uow, version, requested_by=None, charge=False
                        )
                    await uow.commit()
                scheduled[organization.alias] = len(versions)
            offset += page

    async def waiting_for_model(self, budget: RequestBudget) -> int:
        """Check again the documents whose legal checks waited for the model's
        daily allowance, as many as today's remaining requests allow (about one
        request a document)."""
        allowance = await budget.remaining_today()
        if allowance is not None and allowance <= 0:
            return 0
        scheduled = 0
        offset, page = 0, 100
        while True:
            async with self._uow_factory.for_platform() as uow:
                organizations = await uow.organizations.list_all(limit=page, offset=offset)
            if not organizations:
                return scheduled
            for organization in organizations:
                async with self._uow_factory.for_tenant(organization.id) as uow:
                    for version in await uow.versions.latest_waiting_for_model():
                        if allowance is not None and scheduled >= allowance:
                            await uow.commit()
                            return scheduled
                        await self._scheduler.schedule(
                            uow, version, requested_by=None, charge=False
                        )
                        scheduled += 1
                    await uow.commit()
            offset += page


class ResumeWaitingChecks:
    """The hourly job: once the model's allowance renews, the checks that
    waited for it run again (and the rest wait for the next hour)."""

    def __init__(self, recheck: RecheckDocuments, budget: RequestBudget) -> None:
        self._recheck = recheck
        self._budget = budget

    async def __call__(self, payload: JobPayload) -> None:
        scheduled = await self._recheck.waiting_for_model(self._budget)
        if scheduled:
            log.info("checks.resumed", documents=scheduled)
