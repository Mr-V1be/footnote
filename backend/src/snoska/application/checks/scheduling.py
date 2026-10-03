from __future__ import annotations

from uuid import UUID

from snoska.application.billing.meter import Charge, UsageMeter
from snoska.application.shared.jobs import RUN_CHECKS
from snoska.domain.billing.plans import UsageMetric
from snoska.domain.billing.usage import LedgerReason, QuotaExceededError, counted_pages
from snoska.domain.checks.catalog import CheckCatalog
from snoska.domain.checks.run import CheckRun, RunFailureCode
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

    def __init__(self, catalog: CheckCatalog, clock: Clock, meter: UsageMeter) -> None:
        self._catalog = catalog
        self._clock = clock
        self._meter = meter

    async def schedule(
        self,
        uow: UnitOfWork,
        version: DocumentVersion,
        requested_by: UUID | None,
        *,
        charge: bool = True,
    ) -> CheckRun:
        """Queue a run; with ``charge`` it counts against the plan first and
        raises QuotaExceededError when the month's allowance is used up."""
        pending = await uow.check_runs.pending_for_version(version.id)
        if pending is not None:
            return pending
        run = self._new_run(version, requested_by)
        if charge:
            await self._meter.consume(
                uow,
                version.organization_id,
                (Charge(UsageMetric.CHECKS, 1), Charge(UsageMetric.PAGES, pages_of(version))),
                LedgerReason.CHECK_RUN,
                reference=str(run.id),
            )
        await uow.check_runs.add(run)
        await uow.outbox.add(
            OutboxMessage(
                id=new_id(),
                job_name=RUN_CHECKS.name,
                payload={"organization_id": str(run.organization_id), "run_id": str(run.id)},
                created_at=run.created_at,
            )
        )
        return run

    def _new_run(self, version: DocumentVersion, requested_by: UUID | None) -> CheckRun:
        now = self._clock.now()
        return CheckRun.queue(
            id=new_id(),
            organization_id=version.organization_id,
            document_id=version.document_id,
            version_id=version.id,
            catalog_revision=self._catalog.revision,
            requested_by=requested_by,
            now=now,
        )

    async def on_parsed(self, uow: UnitOfWork, version: DocumentVersion) -> None:
        """Every parsed version is checked straight away; past the plan's
        limit the run is recorded as failed for that reason, so the document
        says why it was not checked."""
        try:
            await self.schedule(uow, version, requested_by=None)
        except QuotaExceededError:
            run = self._new_run(version, requested_by=None)
            run.fail(RunFailureCode.QUOTA_EXCEEDED, self._clock.now())
            await uow.check_runs.add(run)


def pages_of(version: DocumentVersion) -> int:
    summary = version.summary
    if summary is None:
        return 1
    return counted_pages(summary.page_count, summary.character_count)
