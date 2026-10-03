from __future__ import annotations

from snoska.application.checks.scheduling import CheckScheduler
from snoska.ports.unit_of_work import UnitOfWorkFactory


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
