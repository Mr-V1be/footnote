from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID

import structlog

from footnote.application.checks.embeddings import TenantEmbeddings
from footnote.application.checks.engine import CheckEngine, DocumentUnderCheck, Executed
from footnote.application.checks.recording import findings_of, result_of
from footnote.application.shared.jobs import RUN_CHECKS
from footnote.domain.checks.catalog import CheckCatalog, CheckDefinition, CheckMethod
from footnote.domain.checks.finding import Finding
from footnote.domain.checks.run import CheckRun, RunFailureCode
from footnote.domain.documents.requisites import RequisiteDetector
from footnote.domain.documents.structure import DocumentStructure
from footnote.domain.documents.version import ParseStatus
from footnote.ports.clock import Clock
from footnote.ports.jobs import JobPayload
from footnote.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

log = structlog.get_logger(__name__)

# Deliveries the queue makes of one run before it gives up.
MAX_RUN_ATTEMPTS = RUN_CHECKS.max_retries + 1


@dataclass(frozen=True, slots=True)
class _Prepared:
    run: CheckRun
    document: DocumentUnderCheck
    pending: tuple[CheckDefinition, ...]
    next_ordinal: int
    earlier: dict[str, Finding]


class RunSettledHook(Protocol):
    """Called in the transaction that settles a run (completed or failed)."""

    async def on_settled(self, uow: UnitOfWork, run: CheckRun) -> None: ...


class RunChecks:
    """Background job: run the applicable checks on a document version.

    Each check's result is stored in its own transaction as soon as it is
    known, together with the progress counter, so the interface sees results
    arrive one by one. A redelivered job resumes after the last stored result.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: CheckCatalog,
        engine: CheckEngine,
        detector: RequisiteDetector,
        clock: Clock,
        model_name: str,
        settled: RunSettledHook | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._engine = engine
        self._detector = detector
        self._clock = clock
        self._model_name = model_name
        self._settled = settled

    async def __call__(self, payload: JobPayload) -> None:
        organization_id = UUID(payload["organization_id"])
        run_id = UUID(payload["run_id"])
        prepared = await self._prepare(organization_id, run_id)
        if prepared is None:
            return
        bound = log.bind(run_id=str(run_id), organization_id=str(organization_id))
        next_ordinal = prepared.next_ordinal

        async def record(executed: Executed) -> None:
            nonlocal next_ordinal
            stored = await self._record(prepared, executed, next_ordinal)
            next_ordinal += stored

        await self._engine.run(prepared.document, prepared.pending, record)
        await self._finish(organization_id, run_id)
        bound.info("checks.run_completed", checks=prepared.run.total)

    async def _prepare(self, organization_id: UUID, run_id: UUID) -> _Prepared | None:
        async with self._uow_factory.for_tenant(organization_id) as uow:
            run = await uow.check_runs.lock(run_id)
            if run is None or run.is_settled:
                return None
            if run.attempts >= MAX_RUN_ATTEMPTS:
                # Every delivery the queue makes has failed: say so instead of
                # leaving the run "running" forever.
                log.error("checks.run_failed_finally", run_id=str(run_id))
                run.fail(RunFailureCode.INTERNAL_ERROR, self._clock.now())
                await uow.check_runs.save(run)
                await self._announce(uow, run)
                await uow.commit()
                return None
            version = await uow.versions.get(run.version_id)
            document = await uow.documents.get(run.document_id)
            structure = await uow.structures.load(run.version_id)
            if (
                version is None
                or document is None
                or structure is None
                or version.status is not ParseStatus.PARSED
            ):
                run.fail(RunFailureCode.VERSION_NOT_PARSED, self._clock.now())
                await uow.check_runs.save(run)
                await self._announce(uow, run)
                await uow.commit()
                return None
            checks = self._catalog.applicable(document.kind_code)
            recorded = {
                result.check_code for result in await uow.check_results.list_for_run(run_id)
            }
            run.start(total=len(checks), done=len(recorded), now=self._clock.now())
            await uow.check_runs.save(run)
            next_ordinal = await uow.findings.count_for_run(run_id)
            earlier = dict(await uow.findings.reviewed_before(run.document_id, run_id))
            await uow.commit()
        return _Prepared(
            run=run,
            document=DocumentUnderCheck(
                title=document.title,
                kind=document.kind_code,
                structure=self._with_requisites(structure),
                embeddings=TenantEmbeddings(self._uow_factory, organization_id),
            ),
            pending=tuple(check for check in checks if check.code not in recorded),
            next_ordinal=next_ordinal,
            earlier=earlier,
        )

    def _with_requisites(self, structure: DocumentStructure) -> DocumentStructure:
        return replace(structure, requisites=self._detector.detect(structure.blocks))

    async def _record(self, prepared: _Prepared, executed: Executed, first_ordinal: int) -> int:
        model = self._model_name if executed.check.method is CheckMethod.MODEL else None
        run_id, organization_id = prepared.run.id, prepared.run.organization_id
        async with self._uow_factory.for_tenant(organization_id) as uow:
            run = await uow.check_runs.lock(run_id)
            if run is None or run.is_settled:
                return 0
            await uow.check_results.add(result_of(executed, run, model, self._clock.now()))
            findings = findings_of(
                executed, run, prepared.document.structure, first_ordinal, prepared.earlier
            )
            await uow.findings.add_many(findings)
            run.advance()
            await uow.check_runs.save(run)
            await uow.commit()
        return len(findings)

    async def _finish(self, organization_id: UUID, run_id: UUID) -> None:
        async with self._uow_factory.for_tenant(organization_id) as uow:
            run = await uow.check_runs.lock(run_id)
            if run is None or run.is_settled:
                return
            run.complete(self._clock.now())
            await uow.check_runs.save(run)
            await self._announce(uow, run)
            await uow.commit()

    async def _announce(self, uow: UnitOfWork, run: CheckRun) -> None:
        if self._settled is not None:
            await self._settled.on_settled(uow, run)
