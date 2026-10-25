from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from snoska.api.schemas.billing.billing import PlanOut
from snoska.api.schemas.common import ApiModel
from snoska.application.operations.platform import OrganizationSummary, SystemStatus
from snoska.domain.billing.plans import UsageMetric
from snoska.domain.operations.schedule import EditionCheck, WatchOutcome
from snoska.domain.shared.locale import Locale


class OrganizationRowOut(ApiModel):
    id: UUID
    alias: str
    name: str
    created_at: datetime
    plan_code: str
    period_start: date
    used: dict[UsageMetric, int]
    members: int | None

    @classmethod
    def of(cls, summary: OrganizationSummary) -> OrganizationRowOut:
        organization = summary.organization
        return cls(
            id=organization.id,
            alias=organization.alias,
            name=organization.name,
            created_at=organization.created_at,
            plan_code=summary.plan_code,
            period_start=summary.period_start,
            used=dict(summary.used),
            members=summary.members,
        )


class PlanAssignIn(ApiModel):
    plan: str = Field(min_length=1, max_length=40)


class ActStateOut(ApiModel):
    code: str
    title: str
    revision: str | None
    activated_at: datetime | None
    indexed: bool


class EditionCheckOut(ApiModel):
    act_code: str
    checked_at: datetime
    outcome: WatchOutcome
    revision: str | None
    error: str | None

    @classmethod
    def of(cls, check: EditionCheck) -> EditionCheckOut:
        return cls(
            act_code=check.act_code,
            checked_at=check.checked_at,
            outcome=check.outcome,
            revision=check.revision,
            error=check.error,
        )


class HealthOut(ApiModel):
    name: str
    ok: bool


class SystemOut(ApiModel):
    health: list[HealthOut]
    model_configured: bool
    language_model: str | None
    embedding_model: str | None
    acts: list[ActStateOut]
    edition_checks: list[EditionCheckOut]
    next_corpus_watch: datetime | None
    outbox_pending: int
    model_requests_left: int | None

    @classmethod
    def of(cls, status: SystemStatus, locale: Locale) -> SystemOut:
        return cls(
            health=[HealthOut(name=name, ok=ok) for name, ok in status.health.items()],
            model_configured=status.model_configured,
            language_model=status.language_model,
            embedding_model=status.embedding_model,
            acts=[
                ActStateOut(
                    code=act.code,
                    title=act.title.resolve(locale),
                    revision=act.edition.source_revision if act.edition else None,
                    activated_at=act.edition.activated_at if act.edition else None,
                    indexed=act.indexed,
                )
                for act in status.acts
            ],
            edition_checks=[EditionCheckOut.of(check) for check in status.edition_checks],
            next_corpus_watch=status.next_corpus_watch,
            outbox_pending=status.outbox_pending,
            model_requests_left=status.model_requests_left,
        )


__all__ = ["OrganizationRowOut", "PlanAssignIn", "PlanOut", "SystemOut"]
