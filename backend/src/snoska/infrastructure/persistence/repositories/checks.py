from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, and_, func, insert, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.checks.catalog import CheckMethod, Severity
from snoska.domain.checks.finding import Finding, NormCitation, ReviewStatus
from snoska.domain.checks.outcome import (
    CitedProvision,
    Detail,
    FindingKind,
    ResultStatus,
    TextLocation,
)
from snoska.domain.checks.result import CheckResult
from snoska.domain.checks.run import CheckRun, RunFailureCode, RunStatus
from snoska.infrastructure.persistence.tables.checks import check_results, check_runs, findings
from snoska.ports.checks.repositories import RunSummary
from snoska.ports.unit_of_work import ConcurrentModificationError

PENDING = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)
# Findings still to deal with: open, or accepted and waiting for a fix.
OUTSTANDING_REVIEWS = (ReviewStatus.OPEN.value, ReviewStatus.ACCEPTED.value)


def _run(row: RowMapping) -> CheckRun:
    return CheckRun(
        id=row["id"],
        organization_id=row["organization_id"],
        document_id=row["document_id"],
        version_id=row["version_id"],
        catalog_revision=row["catalog_revision"],
        requested_by=row["requested_by"],
        created_at=row["created_at"],
        status=RunStatus(row["status"]),
        total=row["total"],
        done=row["done"],
        attempts=row["attempts"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        failure_code=RunFailureCode(row["failure_code"]) if row["failure_code"] else None,
        revision=row["revision"],
    )


def _run_state(run: CheckRun) -> dict[str, Any]:
    return {
        "status": run.status.value,
        "total": run.total,
        "done": run.done,
        "attempts": run.attempts,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "failure_code": run.failure_code.value if run.failure_code else None,
    }


def _locations(value: Sequence[TextLocation]) -> list[dict[str, int]]:
    return [{"block": item.block_ordinal, "start": item.start, "end": item.end} for item in value]


def _from_locations(value: Sequence[Mapping[str, int]]) -> tuple[TextLocation, ...]:
    return tuple(TextLocation(item["block"], item["start"], item["end"]) for item in value)


def _result(row: RowMapping) -> CheckResult:
    cited = (
        CitedProvision(
            act_code=row["cited_act"],
            edition_id=row["cited_edition_id"],
            anchor=row["cited_anchor"],
            citation=row["cited_citation"],
        )
        if row["cited_edition_id"] is not None
        else None
    )
    return CheckResult(
        run_id=row["run_id"],
        organization_id=row["organization_id"],
        check_code=row["check_code"],
        method=CheckMethod(row["method"]),
        status=ResultStatus(row["status"]),
        evidence=_from_locations(row["evidence"]),
        cited=cited,
        error_code=row["error_code"],
        attempts=row["attempts"],
        duration_ms=row["duration_ms"],
        model=row["model"],
        finished_at=row["finished_at"],
    )


def _detail(value: Mapping[str, Any]) -> Detail:
    if value.get("text") is not None:
        return Detail.written(str(value["text"]))
    return Detail(code=str(value["code"]), params=dict(value.get("params") or {}))


def _detail_json(detail: Detail) -> dict[str, Any]:
    if detail.text is not None:
        return {"text": detail.text}
    return {"code": detail.code, "params": dict(detail.params)}


def _finding(row: RowMapping) -> Finding:
    location = (
        TextLocation(row["block_ordinal"], row["span_start"], row["span_end"])
        if row["block_ordinal"] is not None
        else None
    )
    return Finding(
        id=row["id"],
        organization_id=row["organization_id"],
        run_id=row["run_id"],
        check_code=row["check_code"],
        kind=FindingKind(row["kind"]),
        severity=Severity(row["severity"]),
        ordinal=row["ordinal"],
        title=row["title"],
        detail=_detail(row["detail"]),
        recommendation=row["recommendation"],
        norm=NormCitation(
            citation=row["norm_citation"],
            act_code=row["norm_act"],
            edition_id=row["norm_edition_id"],
            anchor=row["norm_anchor"],
        ),
        location=location,
        places=_from_locations(row["places"]),
        fingerprint=row["fingerprint"],
        review=ReviewStatus(row["review"]),
        reviewed_by=row["reviewed_by"],
        reviewed_at=row["reviewed_at"],
        revision=row["revision"],
    )


def _finding_row(finding: Finding) -> dict[str, Any]:
    location = finding.location
    return {
        "id": finding.id,
        "organization_id": finding.organization_id,
        "run_id": finding.run_id,
        "check_code": finding.check_code,
        "kind": finding.kind.value,
        "severity": finding.severity.value,
        "ordinal": finding.ordinal,
        "title": finding.title,
        "detail": _detail_json(finding.detail),
        "recommendation": finding.recommendation,
        "norm_citation": finding.norm.citation,
        "norm_act": finding.norm.act_code,
        "norm_edition_id": finding.norm.edition_id,
        "norm_anchor": finding.norm.anchor,
        "block_ordinal": location.block_ordinal if location else None,
        "span_start": location.start if location else None,
        "span_end": location.end if location else None,
        "places": _locations(finding.places),
        "fingerprint": finding.fingerprint,
        "review": finding.review.value,
        "reviewed_by": finding.reviewed_by,
        "reviewed_at": finding.reviewed_at,
        "revision": finding.revision,
    }


class SqlCheckRunRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, run: CheckRun) -> None:
        await self._connection.execute(
            insert(check_runs).values(
                id=run.id,
                organization_id=run.organization_id,
                document_id=run.document_id,
                version_id=run.version_id,
                catalog_revision=run.catalog_revision,
                requested_by=run.requested_by,
                created_at=run.created_at,
                revision=run.revision,
                **_run_state(run),
            )
        )

    async def get(self, run_id: UUID) -> CheckRun | None:
        result = await self._connection.execute(select(check_runs).where(check_runs.c.id == run_id))
        row = result.mappings().first()
        return _run(row) if row else None

    async def lock(self, run_id: UUID) -> CheckRun | None:
        result = await self._connection.execute(
            select(check_runs).where(check_runs.c.id == run_id).with_for_update()
        )
        row = result.mappings().first()
        return _run(row) if row else None

    async def save(self, run: CheckRun) -> None:
        result = await self._connection.execute(
            update(check_runs)
            .where(check_runs.c.id == run.id, check_runs.c.revision == run.revision)
            .values(revision=run.revision + 1, **_run_state(run))
        )
        if result.rowcount != 1:
            raise ConcurrentModificationError("the run was changed concurrently")
        run.revision += 1

    async def pending_for_version(self, version_id: UUID) -> CheckRun | None:
        result = await self._connection.execute(
            select(check_runs).where(
                check_runs.c.version_id == version_id, check_runs.c.status.in_(PENDING)
            )
        )
        row = result.mappings().first()
        return _run(row) if row else None

    async def latest_for_version(self, version_id: UUID) -> CheckRun | None:
        result = await self._connection.execute(
            select(check_runs)
            .where(check_runs.c.version_id == version_id)
            .order_by(check_runs.c.created_at.desc())
            .limit(1)
        )
        row = result.mappings().first()
        return _run(row) if row else None

    async def latest_summaries(self, version_ids: Collection[UUID]) -> Mapping[UUID, RunSummary]:
        if not version_ids:
            return {}
        latest = (
            select(check_runs)
            .where(check_runs.c.version_id.in_(list(version_ids)))
            .ext(distinct_on(check_runs.c.version_id))
            .order_by(check_runs.c.version_id, check_runs.c.created_at.desc())
            .subquery("latest")
        )
        not_performed = (
            select(func.count())
            .where(
                check_results.c.run_id == latest.c.id,
                check_results.c.status == ResultStatus.ERROR.value,
            )
            .scalar_subquery()
            .label("not_performed")
        )
        counts = await self._connection.execute(
            select(
                latest.c.id,
                latest.c.document_id,
                latest.c.version_id,
                latest.c.status,
                latest.c.total,
                latest.c.done,
                not_performed,
                findings.c.kind,
                findings.c.severity,
                func.count(findings.c.id).label("count"),
            )
            .select_from(
                latest.outerjoin(
                    findings,
                    and_(
                        findings.c.run_id == latest.c.id,
                        findings.c.review.in_(OUTSTANDING_REVIEWS),
                    ),
                )
            )
            .group_by(
                latest.c.id,
                latest.c.document_id,
                latest.c.version_id,
                latest.c.status,
                latest.c.total,
                latest.c.done,
                findings.c.kind,
                findings.c.severity,
            )
        )
        severities: dict[UUID, dict[Severity, int]] = {}
        reviews: dict[UUID, int] = {}
        rows: dict[UUID, RowMapping] = {}
        for row in counts.mappings():
            version_id = row["version_id"]
            rows[version_id] = row
            severities.setdefault(version_id, {})
            if row["kind"] == FindingKind.VIOLATION.value:
                severities[version_id][Severity(row["severity"])] = (
                    severities[version_id].get(Severity(row["severity"]), 0) + row["count"]
                )
            elif row["kind"] == FindingKind.REVIEW.value:
                reviews[version_id] = reviews.get(version_id, 0) + row["count"]
        return {
            version_id: RunSummary(
                run_id=row["id"],
                document_id=row["document_id"],
                version_id=version_id,
                status=RunStatus(row["status"]),
                total=row["total"],
                done=row["done"],
                open_by_severity=severities.get(version_id, {}),
                open_reviews=reviews.get(version_id, 0),
                not_performed=row["not_performed"],
            )
            for version_id, row in rows.items()
        }


class SqlCheckResultRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, result: CheckResult) -> None:
        cited = result.cited
        await self._connection.execute(
            insert(check_results).values(
                run_id=result.run_id,
                organization_id=result.organization_id,
                check_code=result.check_code,
                method=result.method.value,
                status=result.status.value,
                evidence=_locations(result.evidence),
                cited_act=cited.act_code if cited else None,
                cited_edition_id=cited.edition_id if cited else None,
                cited_anchor=cited.anchor if cited else None,
                cited_citation=cited.citation if cited else None,
                error_code=result.error_code,
                attempts=result.attempts,
                duration_ms=result.duration_ms,
                model=result.model,
                finished_at=result.finished_at,
            )
        )

    async def list_for_run(self, run_id: UUID) -> Sequence[CheckResult]:
        result = await self._connection.execute(
            select(check_results).where(check_results.c.run_id == run_id)
        )
        return [_result(row) for row in result.mappings()]


class SqlFindingRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add_many(self, items: Sequence[Finding]) -> None:
        if items:
            await self._connection.execute(
                insert(findings), [_finding_row(finding) for finding in items]
            )

    async def get(self, finding_id: UUID) -> Finding | None:
        result = await self._connection.execute(select(findings).where(findings.c.id == finding_id))
        row = result.mappings().first()
        return _finding(row) if row else None

    async def save(self, finding: Finding) -> None:
        result = await self._connection.execute(
            update(findings)
            .where(findings.c.id == finding.id, findings.c.revision == finding.revision)
            .values(
                review=finding.review.value,
                reviewed_by=finding.reviewed_by,
                reviewed_at=finding.reviewed_at,
                revision=finding.revision + 1,
            )
        )
        if result.rowcount != 1:
            raise ConcurrentModificationError("the finding was changed concurrently")
        finding.revision += 1

    async def list_for_run(self, run_id: UUID) -> Sequence[Finding]:
        result = await self._connection.execute(
            select(findings).where(findings.c.run_id == run_id).order_by(findings.c.ordinal)
        )
        return [_finding(row) for row in result.mappings()]

    async def reviewed_before(self, document_id: UUID, run_id: UUID) -> Mapping[str, Finding]:
        current = select(check_runs.c.created_at).where(check_runs.c.id == run_id).scalar_subquery()
        result = await self._connection.execute(
            select(findings)
            .join(check_runs, check_runs.c.id == findings.c.run_id)
            .where(
                check_runs.c.document_id == document_id,
                check_runs.c.created_at < current,
                findings.c.review != ReviewStatus.OPEN.value,
            )
            .order_by(findings.c.reviewed_at.asc())
        )
        # Ascending order: a later decision on the same fingerprint replaces an earlier one.
        return {row["fingerprint"]: _finding(row) for row in result.mappings()}

    async def count_for_run(self, run_id: UUID) -> int:
        result = await self._connection.execute(
            select(func.count()).select_from(findings).where(findings.c.run_id == run_id)
        )
        return int(result.scalar_one())
