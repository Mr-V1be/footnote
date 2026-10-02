from __future__ import annotations

from uuid import UUID

from snoska.application.shared.jobs import RUN_CHECKS
from snoska.domain.checks.catalog import CheckCatalog
from snoska.domain.checks.run import CheckRun
from snoska.domain.documents.version import DocumentVersion
from snoska.domain.shared.ids import new_id
from snoska.ports.clock import Clock
from snoska.ports.outbox import OutboxMessage
from snoska.ports.unit_of_work import UnitOfWork


class CheckScheduler:
    """Queues a run of the current catalogue for a version.

    It works inside the caller's transaction: the run and the job that
    executes it are stored together or not at all. A version has at most one
    waiting or running run; asking again returns that run.
    """

    def __init__(self, catalog: CheckCatalog, clock: Clock) -> None:
        self._catalog = catalog
        self._clock = clock

    async def schedule(
        self, uow: UnitOfWork, version: DocumentVersion, requested_by: UUID | None
    ) -> CheckRun:
        pending = await uow.check_runs.pending_for_version(version.id)
        if pending is not None:
            return pending
        now = self._clock.now()
        run = CheckRun.queue(
            id=new_id(),
            organization_id=version.organization_id,
            document_id=version.document_id,
            version_id=version.id,
            catalog_revision=self._catalog.revision,
            requested_by=requested_by,
            now=now,
        )
        await uow.check_runs.add(run)
        await uow.outbox.add(
            OutboxMessage(
                id=new_id(),
                job_name=RUN_CHECKS.name,
                payload={"organization_id": str(run.organization_id), "run_id": str(run.id)},
                created_at=now,
            )
        )
        return run

    async def on_parsed(self, uow: UnitOfWork, version: DocumentVersion) -> None:
        """Every parsed version is checked straight away."""
        await self.schedule(uow, version, requested_by=None)
