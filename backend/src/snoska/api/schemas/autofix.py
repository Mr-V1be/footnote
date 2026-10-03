from __future__ import annotations

from snoska.api.schemas.common import ApiModel
from snoska.application.autofix.service import AutofixOutcome, AutofixPreview
from snoska.domain.autofix.actions import AppliedChange, ChangeKind, SkipReason


class PlannedFixOut(ApiModel):
    check_code: str
    places: int


class SkippedFixOut(ApiModel):
    check_code: str
    reason: SkipReason
    findings: int


class AutofixPreviewOut(ApiModel):
    # Only DOCX can be corrected; a PDF or a scan is reported as such.
    editable: bool
    planned: list[PlannedFixOut]
    skipped: list[SkippedFixOut]

    @classmethod
    def of(cls, preview: AutofixPreview) -> AutofixPreviewOut:
        return cls(
            editable=preview.editable,
            planned=[
                PlannedFixOut(check_code=item.check_code, places=item.places)
                for item in preview.planned
            ],
            skipped=[
                SkippedFixOut(
                    check_code=item.check_code, reason=item.reason, findings=item.findings
                )
                for item in preview.skipped
            ],
        )


class ChangeOut(ApiModel):
    """One line of a correction's journal: before and after."""

    check_code: str
    kind: ChangeKind
    # The block in the source version (text changes); None for the layout.
    block_ordinal: int | None
    before: str
    after: str
    places: int

    @classmethod
    def of(cls, change: AppliedChange) -> ChangeOut:
        return cls(
            check_code=change.check_code,
            kind=change.kind,
            block_ordinal=change.block_ordinal,
            before=change.before,
            after=change.after,
            places=change.places,
        )


class AutofixOut(ApiModel):
    version: int
    changes: list[ChangeOut]

    @classmethod
    def of(cls, outcome: AutofixOutcome) -> AutofixOut:
        return cls(
            version=outcome.result.version_number,
            changes=[ChangeOut.of(change) for change in outcome.changes],
        )
