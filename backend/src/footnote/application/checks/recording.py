from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from footnote.application.checks.engine import Executed
from footnote.domain.checks.catalog import StandardNorm
from footnote.domain.checks.finding import Finding, NormCitation, ReviewStatus, fingerprint
from footnote.domain.checks.outcome import TextLocation
from footnote.domain.checks.result import CheckResult
from footnote.domain.checks.run import CheckRun
from footnote.domain.documents.structure import DocumentStructure
from footnote.domain.shared.ids import new_id


def quoted(structure: DocumentStructure, location: TextLocation | None) -> str | None:
    """The words a location points at in the stored structure."""
    if location is None:
        return None
    block = next((b for b in structure.blocks if b.ordinal == location.block_ordinal), None)
    return block.text[location.start : location.end] if block else None


def _norm(executed: Executed) -> NormCitation:
    cited, norm = executed.outcome.cited, executed.check.norm
    if cited is not None:
        return NormCitation(
            citation=cited.citation,
            act_code=cited.act_code,
            edition_id=cited.edition_id,
            anchor=cited.anchor,
        )
    if isinstance(norm, StandardNorm):
        return NormCitation(citation=norm.citation)
    raise ValueError(f"{executed.check.code}: a finding on a law must cite its provision")


def result_of(executed: Executed, run: CheckRun, model: str | None, now: datetime) -> CheckResult:
    outcome = executed.outcome
    return CheckResult(
        run_id=run.id,
        organization_id=run.organization_id,
        check_code=executed.check.code,
        method=executed.check.method,
        status=outcome.status,
        evidence=outcome.evidence,
        cited=outcome.cited,
        error_code=outcome.error_code,
        attempts=outcome.attempts,
        duration_ms=executed.duration_ms,
        model=model,
        finished_at=now,
    )


def findings_of(
    executed: Executed,
    run: CheckRun,
    structure: DocumentStructure,
    first_ordinal: int,
    earlier: Mapping[str, Finding],
) -> list[Finding]:
    """Findings of one check, with decisions carried over from earlier runs."""
    check = executed.check
    findings: list[Finding] = []
    for index, draft in enumerate(executed.outcome.findings):
        finding = Finding(
            id=new_id(),
            organization_id=run.organization_id,
            run_id=run.id,
            check_code=check.code,
            kind=draft.kind,
            severity=check.severity,
            ordinal=first_ordinal + index,
            title=check.title,
            detail=draft.detail,
            recommendation=draft.recommendation or check.recommendation,
            norm=_norm(executed),
            location=draft.location,
            places=draft.places,
            fingerprint=fingerprint(check.code, quoted(structure, draft.location)),
            review=ReviewStatus.OPEN,
            reviewed_by=None,
            reviewed_at=None,
            revision=0,
        )
        previous = earlier.get(finding.fingerprint)
        if previous is not None:
            finding.inherit_review(previous)
        findings.append(finding)
    return findings
