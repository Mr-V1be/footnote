from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from snoska.api.schemas.common import ApiModel
from snoska.application.checks.service import CheckReport
from snoska.domain.checks.catalog import CheckCatalog, CheckDefinition, CheckMethod, Severity
from snoska.domain.checks.finding import Finding, ReviewStatus
from snoska.domain.checks.outcome import DetailValue, FindingKind, ResultStatus, TextLocation
from snoska.domain.checks.result import CheckResult
from snoska.domain.checks.run import CheckRun, RunFailureCode, RunStatus
from snoska.domain.shared.locale import Locale, LocalizedText
from snoska.ports.checks.repositories import RunSummary


class LocationOut(ApiModel):
    block_ordinal: int
    start: int
    end: int

    @classmethod
    def of(cls, location: TextLocation) -> LocationOut:
        return cls(block_ordinal=location.block_ordinal, start=location.start, end=location.end)


class RunOut(ApiModel):
    id: UUID
    document_id: UUID
    version_id: UUID
    status: RunStatus
    total: int
    done: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    failure_code: RunFailureCode | None
    catalog_revision: str
    revision: int

    @classmethod
    def of(cls, run: CheckRun) -> RunOut:
        return cls(
            id=run.id,
            document_id=run.document_id,
            version_id=run.version_id,
            status=run.status,
            total=run.total,
            done=run.done,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            failure_code=run.failure_code,
            catalog_revision=run.catalog_revision,
            revision=run.revision,
        )


class ResultOut(ApiModel):
    check_code: str
    method: CheckMethod
    status: ResultStatus
    evidence: list[LocationOut]
    error_code: str | None
    attempts: int
    duration_ms: int
    citation: str | None

    @classmethod
    def of(cls, result: CheckResult, locale: Locale) -> ResultOut:
        return cls(
            check_code=result.check_code,
            method=result.method,
            status=result.status,
            evidence=[LocationOut.of(item) for item in result.evidence],
            error_code=result.error_code,
            attempts=result.attempts,
            duration_ms=result.duration_ms,
            citation=result.cited.citation.resolve(locale) if result.cited else None,
        )


class DetailOut(ApiModel):
    """Either a message code with parameters (translated by the client) or
    text written by the language model, in the language of the request."""

    code: str | None
    params: dict[str, DetailValue]
    text: str | None


class NormOut(ApiModel):
    citation: str
    act_code: str | None
    anchor: str | None
    # The provision's words in the edition the check used; none for standards.
    quote: str | None


class FindingOut(ApiModel):
    """A finding with its texts in the language of the request."""

    id: UUID
    check_code: str
    kind: FindingKind
    severity: Severity
    title: str
    detail: DetailOut
    recommendation: str
    norm: NormOut
    location: LocationOut | None
    # A finding about the whole document lists the places it covers here;
    # they are not marked in the text, only shown on request.
    places: list[LocationOut]
    review: ReviewStatus
    reviewed_at: datetime | None
    revision: int

    @classmethod
    def of(cls, finding: Finding, locale: Locale, quote: str | None = None) -> FindingOut:
        written = finding.detail.text
        return cls(
            id=finding.id,
            check_code=finding.check_code,
            kind=finding.kind,
            severity=finding.severity,
            title=finding.title.resolve(locale),
            detail=DetailOut(
                code=finding.detail.code,
                params=dict(finding.detail.params),
                text=written.resolve(locale) if written else None,
            ),
            recommendation=finding.recommendation.resolve(locale),
            norm=NormOut(
                citation=finding.norm.citation.resolve(locale),
                act_code=finding.norm.act_code,
                anchor=finding.norm.anchor,
                quote=quote,
            ),
            location=LocationOut.of(finding.location) if finding.location else None,
            places=[LocationOut.of(place) for place in finding.places],
            review=finding.review,
            reviewed_at=finding.reviewed_at,
            revision=finding.revision,
        )


class CheckOut(ApiModel):
    """A check of the registry as the product describes it, in the language
    of the request."""

    code: str
    family: str
    method: CheckMethod
    severity: Severity
    kinds: list[str]
    title: str
    requirement: str
    citations: list[str]

    @classmethod
    def of(
        cls,
        check: CheckDefinition,
        citations: Mapping[str, tuple[LocalizedText, ...]],
        locale: Locale,
    ) -> CheckOut:
        return cls(
            code=check.code,
            family=check.family,
            method=check.method,
            severity=check.severity,
            kinds=sorted(check.kinds),
            title=check.title.resolve(locale),
            requirement=check.requirement.resolve(locale),
            citations=[citation.resolve(locale) for citation in citations.get(check.code, ())],
        )


class CheckReportOut(ApiModel):
    run: RunOut
    results: list[ResultOut]
    findings: list[FindingOut]
    checks: list[CheckOut]

    @classmethod
    def of(
        cls,
        report: CheckReport,
        catalog: CheckCatalog,
        citations: Mapping[str, tuple[LocalizedText, ...]],
        locale: Locale,
    ) -> CheckReportOut:
        codes = {result.check_code for result in report.results} | {
            finding.check_code for finding in report.findings
        }
        known = {check.code: check for check in catalog.all()}
        return cls(
            run=RunOut.of(report.run),
            results=[ResultOut.of(result, locale) for result in report.results],
            findings=[
                FindingOut.of(
                    finding,
                    locale,
                    report.quotes.get((finding.norm.edition_id, finding.norm.anchor))
                    if finding.norm.edition_id and finding.norm.anchor
                    else None,
                )
                for finding in report.findings
            ],
            checks=[
                CheckOut.of(known[code], citations, locale)
                for code in sorted(codes)
                if code in known
            ],
        )


class ReviewIn(ApiModel):
    review: ReviewStatus
    revision: int


class FamilyOut(ApiModel):
    code: str
    rank: int


class ModelsOut(ApiModel):
    """Whether model checks can run: a model API is configured and the corpus
    is searchable with its embedding model."""

    configured: bool
    language_model: str | None
    embedding_model: str | None


class CheckCatalogOut(ApiModel):
    revision: str
    families: list[FamilyOut]
    checks: list[CheckOut]
    models: ModelsOut

    @classmethod
    def of(
        cls,
        catalog: CheckCatalog,
        citations: Mapping[str, tuple[LocalizedText, ...]],
        models: ModelsOut,
        locale: Locale,
    ) -> CheckCatalogOut:
        return cls(
            revision=catalog.revision,
            families=[FamilyOut(code=f.code, rank=f.rank) for f in catalog.families()],
            checks=[CheckOut.of(check, citations, locale) for check in catalog.all()],
            models=models,
        )


class RunSummaryOut(ApiModel):
    """The latest run of a document's latest version, for lists."""

    run_id: UUID
    status: RunStatus
    total: int
    done: int
    critical: int
    important: int
    advice: int
    reviews: int
    # Checks of the run that gave no verdict (e.g. no model connected).
    not_performed: int

    @classmethod
    def of(cls, summary: RunSummary) -> RunSummaryOut:
        counts = summary.open_by_severity
        return cls(
            run_id=summary.run_id,
            status=summary.status,
            total=summary.total,
            done=summary.done,
            critical=counts.get(Severity.CRITICAL, 0),
            important=counts.get(Severity.IMPORTANT, 0),
            advice=counts.get(Severity.ADVICE, 0),
            reviews=summary.open_reviews,
            not_performed=summary.not_performed,
        )
