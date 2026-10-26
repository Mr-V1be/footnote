from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from uuid import UUID

from footnote.application.audit.trail import AuditTrail
from footnote.application.billing.meter import Charge, UsageMeter
from footnote.application.documents.queries import VersionNotFoundError
from footnote.application.documents.upload import DocumentUploads, UploadResult
from footnote.application.tenancy.gate import WorkspaceGate
from footnote.domain.audit.event import AuditAction
from footnote.domain.audit.targets import document_target
from footnote.domain.autofix.actions import (
    AppliedChange,
    FixAction,
    FixPlan,
    ReplaceText,
    SkipReason,
)
from footnote.domain.autofix.planning import plan_fixes
from footnote.domain.billing.plans import UsageMetric
from footnote.domain.billing.usage import LedgerReason
from footnote.domain.checks.catalog import CheckCatalog
from footnote.domain.checks.run import RunStatus
from footnote.domain.documents.document import Document
from footnote.domain.documents.version import DocumentVersion, ParseStatus
from footnote.domain.shared.errors import InvalidStateError
from footnote.domain.shared.locale import Locale
from footnote.domain.tenancy.access import OrganizationAccess
from footnote.domain.tenancy.organization import UserProfile
from footnote.domain.tenancy.permissions import Permission
from footnote.ports.autofix.patching import DocumentPatcher
from footnote.ports.blob_storage import BlobStorage
from footnote.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

# The name a corrected copy is saved under, after the original's.
FIXED_SUFFIX: Mapping[Locale, str] = {Locale.RU: "исправлено", Locale.EN: "fixed"}


class NothingToFixError(InvalidStateError):
    code = "nothing_to_fix"


class NotCheckedYetError(InvalidStateError):
    code = "not_checked_yet"


@dataclass(frozen=True, slots=True)
class PlannedFix:
    check_code: str
    places: int


@dataclass(frozen=True, slots=True)
class SkippedFix:
    check_code: str
    reason: SkipReason
    findings: int


@dataclass(frozen=True, slots=True)
class AutofixPreview:
    """What a correction of a checked version would do, before it is made."""

    editable: bool
    planned: Sequence[PlannedFix]
    skipped: Sequence[SkippedFix]


@dataclass(frozen=True, slots=True)
class AutofixOutcome:
    result: UploadResult
    changes: Sequence[AppliedChange]


@dataclass(frozen=True, slots=True)
class _Source:
    document: Document
    version: DocumentVersion
    plan: FixPlan


def _places(action: FixAction) -> int:
    return 1 if isinstance(action, ReplaceText) else len(getattr(action, "block_ordinals", ())) or 1


class Autofix:
    """Correcting the formatting of a checked DOCX automatically.

    Only deterministic formatting findings that are still open (or accepted)
    are corrected, and only where it is safe; the result is a new version of
    the document with a journal of what changed. The source version is kept
    as it was.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        blobs: BlobStorage,
        uploads: DocumentUploads,
        patcher: DocumentPatcher,
        catalog: CheckCatalog,
        gate: WorkspaceGate,
        meter: UsageMeter,
        audit: AuditTrail,
    ) -> None:
        self._uow_factory = uow_factory
        self._blobs = blobs
        self._uploads = uploads
        self._patcher = patcher
        self._catalog = catalog
        self._gate = gate
        self._meter = meter
        self._audit = audit

    async def preview(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> AutofixPreview:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            source = await self._source(uow, access, document_id, version_number, read_only=True)
        planned: Counter[str] = Counter()
        for action in source.plan.actions:
            planned[action.check_code] += _places(action)
        skipped: Counter[tuple[str, SkipReason]] = Counter(
            (item.check_code, item.reason) for item in source.plan.skipped
        )
        return AutofixPreview(
            editable=source.version.file.format_code == self._patcher.format_code,
            planned=[PlannedFix(code, places) for code, places in planned.items()],
            skipped=[SkippedFix(code, reason, count) for (code, reason), count in skipped.items()],
        )

    async def apply(
        self,
        access: OrganizationAccess,
        author: UserProfile,
        document_id: UUID,
        version_number: int,
        locale: Locale,
    ) -> AutofixOutcome:
        """A corrected copy as a new version, its file named in the author's language."""
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            source = await self._source(uow, access, document_id, version_number, read_only=False)
            structure = await uow.structures.load(source.version.id)
        if source.plan.empty or structure is None:
            raise NothingToFixError("no finding of this version can be corrected automatically")
        content = await self._blobs.read(source.version.file.blob_key)
        patched = await self._patcher.apply(content, source.plan, structure)
        if not patched.changes:
            raise NothingToFixError("the corrections could not be applied to the file")
        stem = PurePath(source.version.file.filename).stem
        filename = f"{stem} ({FIXED_SUFFIX[locale]}).docx"

        async def record(uow: UnitOfWork, document: Document, version: DocumentVersion) -> None:
            await self._meter.consume(
                uow,
                access.organization_id,
                (Charge(UsageMetric.AUTOFIXES, 1),),
                LedgerReason.AUTOFIX,
                reference=str(version.id),
            )
            await uow.changes.record(version.id, patched.changes)
            await self._audit.record(
                uow,
                access,
                AuditAction.DOCUMENT_AUTOFIXED,
                document_target(document),
                {
                    "from_version": version_number,
                    "version": version.number,
                    "changes": len(patched.changes),
                },
            )

        result = await self._uploads.add_generated_version(
            access,
            author,
            document_id=document_id,
            filename=filename,
            content=patched.content,
            derived_from=version_number,
            record=record,
        )
        return AutofixOutcome(result=result, changes=patched.changes)

    async def changes(
        self, access: OrganizationAccess, document_id: UUID, version_number: int
    ) -> Sequence[AppliedChange]:
        """The journal of the correction that made this version (empty otherwise)."""
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._gate.require_document(uow, access, document_id, Permission.DOCUMENTS_READ)
            version = await uow.versions.get_by_number(document_id, version_number)
            if version is None:
                raise VersionNotFoundError("version not found")
            return await uow.changes.list_for_version(version.id)

    async def _source(
        self,
        uow: UnitOfWork,
        access: OrganizationAccess,
        document_id: UUID,
        version_number: int,
        *,
        read_only: bool,
    ) -> _Source:
        permission = Permission.DOCUMENTS_READ if read_only else Permission.DOCUMENTS_UPLOAD
        document = await self._gate.require_document(uow, access, document_id, permission)
        version = await uow.versions.get_by_number(document_id, version_number)
        if version is None:
            raise VersionNotFoundError("version not found")
        run = await uow.check_runs.latest_for_version(version.id)
        structure = await uow.structures.load(version.id)
        if (
            version.status is not ParseStatus.PARSED
            or structure is None
            or run is None
            or run.status is not RunStatus.COMPLETED
        ):
            raise NotCheckedYetError("the version has no completed check")
        findings = await uow.findings.list_for_run(run.id)
        plan = plan_fixes(
            self._catalog,
            findings,
            structure,
            editable=version.file.format_code == self._patcher.format_code,
        )
        return _Source(document=document, version=version, plan=plan)
