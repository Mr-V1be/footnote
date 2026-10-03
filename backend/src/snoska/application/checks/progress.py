from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from snoska.application.checks.service import RunNotFoundError
from snoska.application.tenancy.gate import WorkspaceGate
from snoska.domain.checks.run import CheckRun
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.checks.events import RunChangeFeed, RunChanges
from snoska.ports.unit_of_work import UnitOfWorkFactory

# Without a notification the run is read again this often, so a missed
# notification delays an update but never stalls the stream.
FALLBACK_POLL_SECONDS = 10.0


class RunProgress:
    """A run's state as it changes, until it is settled.

    The stream subscribes to changes before the first read, so nothing that
    happens in between is missed. Every yielded run is read from the database
    under the caller's tenant: notifications only say *which* run changed.
    """

    def __init__(
        self, uow_factory: UnitOfWorkFactory, feed: RunChangeFeed, gate: WorkspaceGate
    ) -> None:
        self._uow_factory = uow_factory
        self._feed = feed
        self._gate = gate

    async def _load(self, organization_id: UUID, run_id: UUID) -> CheckRun:
        async with self._uow_factory.for_tenant(organization_id) as uow:
            run = await uow.check_runs.get(run_id)
        if run is None:
            raise RunNotFoundError("check run not found")
        return run

    async def stream(self, access: OrganizationAccess, run_id: UUID) -> AsyncIterator[CheckRun]:
        organization_id = access.organization_id
        async with self._uow_factory.for_tenant(organization_id) as uow:
            first = await uow.check_runs.get(run_id)
            if first is None:
                raise RunNotFoundError("check run not found")
            await self._gate.require_document(
                uow, access, first.document_id, Permission.DOCUMENTS_READ
            )
        async with self._feed.subscribe() as changes:
            run = await self._load(organization_id, run_id)
            yield run
            while not run.is_settled:
                await self._next_change(changes, run_id)
                latest = await self._load(organization_id, run_id)
                if latest.revision != run.revision:
                    run = latest
                    yield run

    @staticmethod
    async def _next_change(changes: RunChanges, run_id: UUID) -> None:
        """Wait for a change of this run, or until it is time to read it anyway."""
        deadline = asyncio.get_running_loop().time() + FALLBACK_POLL_SECONDS
        while (left := deadline - asyncio.get_running_loop().time()) > 0:
            change = await changes.next(left)
            if change is None or change.run_id == run_id:
                return
