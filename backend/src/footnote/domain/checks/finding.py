from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from footnote.domain.checks.catalog import Severity
from footnote.domain.checks.outcome import Detail, FindingKind, TextLocation
from footnote.domain.shared.errors import ValidationError
from footnote.domain.shared.locale import LocalizedText
from footnote.domain.shared.text import normalize_text
from footnote.domain.tenancy.permissions import Permission


class ReviewStatus(StrEnum):
    """What the team decided about a finding."""

    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FIXED = "fixed"


class UnchangedReviewError(ValidationError):
    code = "review_unchanged"


# Who may set a status: accepting or rejecting is a legal judgement, marking
# fixed (or reopening) is work on the document.
REVIEW_PERMISSIONS: dict[ReviewStatus, Permission] = {
    ReviewStatus.ACCEPTED: Permission.FINDINGS_DECIDE,
    ReviewStatus.REJECTED: Permission.FINDINGS_DECIDE,
    ReviewStatus.FIXED: Permission.FINDINGS_RESOLVE,
    ReviewStatus.OPEN: Permission.FINDINGS_RESOLVE,
}


@dataclass(frozen=True, slots=True)
class NormCitation:
    """The norm a finding rests on.

    For a law, ``edition_id`` and ``anchor`` point at an immutable provision of
    the corpus, so its quote is always the text that was in force when the
    check ran. For a standard, ``citation`` names the clause. The citation
    reads as each interface language cites it.
    """

    citation: LocalizedText
    act_code: str | None = None
    edition_id: UUID | None = None
    anchor: str | None = None


@dataclass(slots=True)
class Finding:
    """A remark on a document version, produced by one check of a run.

    Its texts are those of the catalogue (or the model) when the check ran,
    kept in every interface language.
    """

    id: UUID
    organization_id: UUID
    run_id: UUID
    check_code: str
    kind: FindingKind
    severity: Severity
    ordinal: int
    title: LocalizedText
    detail: Detail
    recommendation: LocalizedText
    norm: NormCitation
    location: TextLocation | None
    fingerprint: str
    review: ReviewStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    revision: int
    # For a finding about the whole document: the places it covers.
    places: tuple[TextLocation, ...] = ()

    def set_review(self, status: ReviewStatus, actor: UUID, now: datetime) -> None:
        if status is self.review:
            raise UnchangedReviewError(f"finding is already {status}")
        self.review = status
        self.reviewed_by = actor
        self.reviewed_at = now

    def inherit_review(self, previous: Finding) -> None:
        """Carry a decision over from the same finding of an earlier run.

        A rejected false positive stays rejected after a re-check; so does an
        accepted one. "Fixed" is not inherited: if the finding is still there,
        the fix did not land.
        """
        if previous.review in (ReviewStatus.ACCEPTED, ReviewStatus.REJECTED):
            self.review = previous.review
            self.reviewed_by = previous.reviewed_by
            self.reviewed_at = previous.reviewed_at


def fingerprint(check_code: str, quote: str | None) -> str:
    """Identity of a finding across runs: the check and the words it points at."""
    return f"{check_code}|{normalize_text(quote).casefold() if quote else ''}"
