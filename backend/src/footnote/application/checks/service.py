from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from footnote.application.audit.trail import AuditTrail
from footnote.application.checks.norms import NormLibrary
from footnote.application.checks.scheduling import CheckScheduler
from footnote.application.documents.queries import VersionNotFoundError
from footnote.application.integrations.events import OrganizationEvents
from footnote.application.tenancy.gate import WorkspaceGate
from footnote.domain.audit.event import AuditAction
from footnote.domain.audit.targets import document_target
from footnote.domain.checks.catalog import CheckCatalog, StandardNorm
from footnote.domain.checks.finding import REVIEW_PERMISSIONS, Finding, ReviewStatus
from footnote.domain.checks.result import CheckResult
from footnote.domain.checks.run import CheckRun
from footnote.domain.documents.version import ParseStatus
from footnote.domain.integrations.webhooks import WebhookEvent
from footnote.domain.shared.errors import InvalidStateError, NotFoundError
from footnote.domain.shared.locale import SOURCE_LOCALE, LocalizedText
from footnote.domain.tenancy.access import OrganizationAccess
from footnote.domain.tenancy.permissions import Permission
from footnote.ports.checks.repositories import RunSummary
from footnote.ports.clock import Clock
from footnote.ports.unit_of_work import ConcurrentModificationError, UnitOfWorkFactory


class RunNotFoundError(NotFoundError):
    code = "check_run_not_found"


class FindingNotFoundError(NotFoundError):
    code = "finding_not_found"


class VersionNotReadyError(InvalidStateError):
    code = "version_not_parsed"


@dataclass(frozen=True, slots=True)
class CheckReport:
    """Everything the result screen shows for one run.

    ``quotes`` hold the provisions findings rest on, by (edition, anchor), as
    worded in the edition that was in force when the check ran.
    """

    run: CheckRun
    results: Sequence[CheckResult]
    findings: Sequence[Finding]
    quotes: Mapping[tuple[UUID, str], str]


class CheckService:
    """Running checks on request, reading their results, reviewing findings."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: CheckCatalog,
        scheduler: CheckScheduler,
        norms: NormLibrary,
        clock: Clock,
        gate: WorkspaceGate,
        audit: AuditTrail,
        events: OrganizationEvents,
    ) -> None:
        self._uow_factory = uow_factory
        self.catalog = catalog
        self._scheduler = scheduler
        self._norms = norms
        self._clock = clock
        self._gate = gate
        self._audit = audit
        self._events = events

    async def request(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> CheckRun:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            document = await self._gate.require_document(
                uow, access, document_id, Permission.CHECKS_RUN
            )
            version = await uow.versions.get_by_number(document_id, version_number)
            if version is None:
                raise VersionNotFoundError("version not found")
            if version.status is not ParseStatus.PARSED:
                raise VersionNotReadyError("the version is not parsed yet")
            run = await self._scheduler.schedule(uow, version, requested_by=access.user_id)
            await self._audit.record(
                uow,
                access,
                AuditAction.CHECK_REQUESTED,
                document_target(document),
                {"version": version_number},
            )
            await uow.commit()
        return run

    async def run(self, access: OrganizationAccess, run_id: UUID) -> CheckRun:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            run = await uow.check_runs.get(run_id)
            if run is None:
                raise RunNotFoundError("check run not found")
            await self._gate.require_document(
                uow, access, run.document_id, Permission.DOCUMENTS_READ
            )
        return run

    async def latest(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> CheckReport | None:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._gate.require_document(uow, access, document_id, Permission.DOCUMENTS_READ)
            version = await uow.versions.get_by_number(document_id, version_number)
            if version is None:
                raise VersionNotFoundError("version not found")
            run = await uow.check_runs.latest_for_version(version.id)
            if run is None:
                return None
            results = await uow.check_results.list_for_run(run.id)
            findings = await uow.findings.list_for_run(run.id)
        references = {
            (finding.norm.edition_id, finding.norm.anchor)
            for finding in findings
            if finding.norm.edition_id is not None and finding.norm.anchor is not None
        }
        provisions = await self._norms.quotes(references)
        return CheckReport(
            run=run,
            results=results,
            findings=findings,
            quotes={key: provision.text for key, provision in provisions.items()},
        )

    def citations(self) -> Mapping[str, tuple[LocalizedText, ...]]:
        """What each check of the catalogue refers to, as it is cited."""
        cited: dict[str, tuple[LocalizedText, ...]] = {}
        for check in self.catalog.all():
            norm = check.norm
            if isinstance(norm, StandardNorm):
                cited[check.code] = (norm.citation,)
            else:
                cited[check.code] = tuple(
                    self._norms.cite(norm.act_code, anchor) for anchor in norm.anchors
                )
        return cited

    async def summaries(
        self, access: OrganizationAccess, version_ids: Collection[UUID]
    ) -> Mapping[UUID, RunSummary]:
        access.require(Permission.DOCUMENTS_READ)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            return await uow.check_runs.latest_summaries(version_ids)

    async def review(
        self, access: OrganizationAccess, finding_id: UUID, status: ReviewStatus, revision: int
    ) -> Finding:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            finding = await uow.findings.get(finding_id)
            run = await uow.check_runs.get(finding.run_id) if finding is not None else None
            if finding is None or run is None:
                raise FindingNotFoundError("finding not found")
            document = await self._gate.require_document(
                uow, access, run.document_id, REVIEW_PERMISSIONS[status]
            )
            if finding.revision != revision:
                raise ConcurrentModificationError("the finding was reviewed by someone else")
            previous = finding.review
            finding.set_review(status, access.user_id, self._clock.now())
            await uow.findings.save(finding)
            await self._audit.record(
                uow,
                access,
                AuditAction.FINDING_REVIEWED,
                document_target(document),
                {
                    "finding": finding.title.resolve(SOURCE_LOCALE),
                    "from": previous.value,
                    "to": status.value,
                },
            )
            await self._events.emit(
                uow,
                access.organization_id,
                WebhookEvent.FINDING_REVIEWED,
                {
                    "finding_id": str(finding.id),
                    "document_id": str(document.id),
                    "check": finding.check_code,
                    "review": status.value,
                },
            )
            await uow.commit()
        return finding
