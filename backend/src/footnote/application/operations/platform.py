from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from footnote.application.billing.service import BillingService
from footnote.application.operations.scheduler import PeriodicScheduler
from footnote.domain.billing.plans import Plan, UsageMetric
from footnote.domain.corpus.acts import Edition
from footnote.domain.corpus.embedding import EmbeddingSpace
from footnote.domain.operations.schedule import EditionCheck
from footnote.domain.shared.locale import LocalizedText
from footnote.domain.tenancy.access import PlatformAccess
from footnote.domain.tenancy.organization import Organization
from footnote.domain.tenancy.permissions import Permission
from footnote.ports.ai import RequestBudget
from footnote.ports.health import HealthCheck
from footnote.ports.identity import OrganizationDirectory
from footnote.ports.unit_of_work import UnitOfWorkFactory

ORGANIZATIONS_LISTED = 200
CHECKS_LISTED = 8
CORPUS_WATCH = "corpus.watch"


@dataclass(frozen=True, slots=True)
class OrganizationSummary:
    organization: Organization
    plan_code: str
    period_start: date
    used: Mapping[UsageMetric, int]
    members: int | None


@dataclass(frozen=True, slots=True)
class ActState:
    code: str
    title: LocalizedText
    edition: Edition | None
    indexed: bool


@dataclass(frozen=True, slots=True)
class SystemStatus:
    health: Mapping[str, bool]
    model_configured: bool
    language_model: str | None
    embedding_model: str | None
    acts: Sequence[ActState]
    edition_checks: Sequence[EditionCheck]
    next_corpus_watch: datetime | None
    outbox_pending: int
    model_requests_left: int | None = None


class PlatformConsole:
    """What the platform's operator sees and does: organizations and their
    plans, the plan catalogue and the state of the system."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        billing: BillingService,
        directory: OrganizationDirectory,
        health: Sequence[HealthCheck],
        scheduler: PeriodicScheduler,
        *,
        model_configured: bool,
        language_model: str | None,
        embedding_model: str | None,
        embedding_space: EmbeddingSpace,
        budget: RequestBudget | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._billing = billing
        self._directory = directory
        self._health = health
        self._scheduler = scheduler
        self._model = (model_configured, language_model, embedding_model)
        self._budget = budget
        self._space = embedding_space

    async def organizations(self, access: PlatformAccess) -> Sequence[OrganizationSummary]:
        access.require(Permission.PLATFORM_TENANTS_READ)
        async with self._uow_factory.for_platform() as uow:
            organizations = await uow.organizations.list_all(limit=ORGANIZATIONS_LISTED, offset=0)
        summaries: list[OrganizationSummary] = []
        for organization in organizations:
            subscription, used = await self._billing.usage_of(organization.id)
            try:
                members: int | None = len(await self._directory.list_members(organization.id))
            except Exception:  # the directory is optional for this view
                members = None
            summaries.append(
                OrganizationSummary(
                    organization=organization,
                    plan_code=subscription.plan_code,
                    period_start=subscription.period_start,
                    used=used,
                    members=members,
                )
            )
        return summaries

    def plans(self, access: PlatformAccess) -> Sequence[Plan]:
        access.require(Permission.PLATFORM_TENANTS_READ)
        return self._billing.plans.all()

    async def assign_plan(self, access: PlatformAccess, organization_id: UUID, plan: str) -> None:
        access.require(Permission.PLATFORM_PLANS_MANAGE)
        await self._billing.assign(organization_id, plan, access.actor)

    async def system(self, access: PlatformAccess) -> SystemStatus:
        access.require(Permission.PLATFORM_SYSTEM_READ)
        results = await asyncio.gather(*(check.check() for check in self._health))
        async with self._uow_factory.for_platform() as uow:
            overviews = await uow.corpus.list_acts()
            indexed = {
                overview.act.code: await uow.corpus.is_indexed(
                    overview.active_edition.id, self._space
                )
                for overview in overviews
                if overview.active_edition is not None
            }
            checks = await uow.edition_checks.latest(limit=CHECKS_LISTED)
            pending = await uow.outbox.pending_count()
        watch = await self._scheduler.next_run(CORPUS_WATCH)
        configured, language_model, embedding_model = self._model
        return SystemStatus(
            health={check.name: ok for check, ok in zip(self._health, results, strict=True)},
            model_configured=configured,
            language_model=language_model,
            embedding_model=embedding_model,
            acts=[
                ActState(
                    code=overview.act.code,
                    title=overview.act.short_title,
                    edition=overview.active_edition,
                    indexed=indexed.get(overview.act.code, False),
                )
                for overview in overviews
            ],
            edition_checks=checks,
            next_corpus_watch=watch.next_run_at if watch else None,
            outbox_pending=pending,
            model_requests_left=await self._budget.remaining_today() if self._budget else None,
        )
