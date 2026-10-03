from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from snoska.application.audit.trail import AuditTrail
from snoska.application.checks.norms import NormLibrary
from snoska.application.checks.scheduling import CheckScheduler
from snoska.application.documents.queries import VersionNotFoundError
from snoska.application.tenancy.gate import WorkspaceGate
from snoska.domain.audit.event import AuditAction
from snoska.domain.audit.targets import document_target
from snoska.domain.checks.catalog import CheckCatalog, LawNorm, StandardNorm
from snoska.domain.checks.finding import REVIEW_PERMISSIONS, Finding, ReviewStatus
from snoska.domain.checks.result import CheckResult
from snoska.domain.checks.run import CheckRun
from snoska.domain.documents.version import ParseStatus
from snoska.domain.shared.errors import InvalidStateError, NotFoundError
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.checks.repositories import RunSummary
from snoska.ports.clock import Clock
from snoska.ports.unit_of_work import ConcurrentModificationError, UnitOfWorkFactory


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
    ) -> None:
        self._uow_factory = uow_factory
        self.catalog = catalog
        self._scheduler = scheduler
        self._norms = norms
        self._clock = clock
        self._gate = gate
        self._audit = audit

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

    async def citations(self) -> Mapping[str, tuple[str, ...]]:
        """What each check of the catalogue refers to, as it is cited."""
        cited: dict[str, tuple[str, ...]] = {}
        anchors_by_act: dict[str, set[str]] = {}
        for check in self.catalog.all():
            if isinstance(check.norm, StandardNorm):
                cited[check.code] = (check.norm.citation,)
            else:
                anchors_by_act.setdefault(check.norm.act_code, set()).update(check.norm.anchors)
        resolved = {
            act: await self._norms.citations(act, anchors)
            for act, anchors in anchors_by_act.items()
        }
        for check in self.catalog.all():
            if isinstance(check.norm, LawNorm):
                found = resolved.get(check.norm.act_code, {})
                cited[check.code] = tuple(
                    found.get(anchor, anchor) for anchor in check.norm.anchors
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
                {"finding": finding.title, "from": previous.value, "to": status.value},
            )
            await uow.commit()
        return finding
