from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.application.ask.service import NormQuestions
from snoska.application.audit.queries import AuditQueries
from snoska.application.autofix.service import Autofix
from snoska.application.billing.service import BillingService
from snoska.application.checks.progress import RunProgress
from snoska.application.checks.quality.benchmark import CheckBenchmark
from snoska.application.checks.quality.queries import QualityQueries
from snoska.application.checks.recheck import RecheckDocuments
from snoska.application.checks.service import CheckService
from snoska.application.corpus.indexing import IndexCorpusEdition
from snoska.application.corpus.queries import CorpusQueries
from snoska.application.corpus.search import NormSearch
from snoska.application.corpus.sync import CorpusSync
from snoska.application.documents.catalog import CatalogQuery
from snoska.application.documents.parsing import ParseDocumentVersion
from snoska.application.documents.queries import DocumentQueries
from snoska.application.documents.upload import DocumentUploads, UploadLimits
from snoska.application.integrations.api_keys import ApiKeys
from snoska.application.integrations.delivery import DeliverWebhook
from snoska.application.integrations.events import FollowUps
from snoska.application.integrations.webhooks import WebhookEndpoints
from snoska.application.shared.jobs import (
    DELIVER_WEBHOOK,
    INDEX_CORPUS_EDITION,
    NOTIFY_TEST_PAYMENT,
    PARSE_DOCUMENT_VERSION,
    RUN_CHECKS,
)
from snoska.application.shared.outbox_relay import OutboxRelay
from snoska.application.tenancy.access import DefaultWorkspace, TenantAccessService
from snoska.application.tenancy.members import OrganizationMembers
from snoska.application.tenancy.platform import PlatformTenantQueries
from snoska.application.tenancy.workspaces import Workspaces
from snoska.bootstrap.assembly.checks import build_checks, check_engine, load_check_catalog
from snoska.bootstrap.assembly.core import Core, Overrides, app_database, build_core
from snoska.bootstrap.providers import AiAdapters
from snoska.bootstrap.settings import Settings
from snoska.domain.documents.formats import SUPPORTED_FORMATS
from snoska.domain.documents.kinds import DOCUMENT_KINDS
from snoska.domain.documents.requisites import RequisiteDetector
from snoska.domain.tenancy.access import AccessPolicy
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES, PLATFORM_ROLES
from snoska.infrastructure.autofix.docx_patcher import DocxPatcher
from snoska.infrastructure.billing.test_gateway import TestGateway
from snoska.infrastructure.billing.test_provider import TestPaymentNotifier, TestPaymentProvider
from snoska.infrastructure.corpus_sources.catalog import YamlActCatalog
from snoska.infrastructure.corpus_sources.pravo_ips import (
    PravoIpsClient,
    PravoIpsConfig,
    PravoIpsSource,
)
from snoska.infrastructure.corpus_sources.snapshot import SnapshotSource
from snoska.infrastructure.integrations.http_transport import HttpWebhookTransport
from snoska.infrastructure.persistence.health import DatabaseHealth
from snoska.infrastructure.storage.health import StorageHealth
from snoska.ports.corpus_source import CorpusSource
from snoska.ports.health import HealthCheck
from snoska.ports.identity import IdentityProvisioning, TokenVerifier
from snoska.ports.jobs import JobHandler, JobPublisher

__all__ = [
    "Container",
    "Overrides",
    "app_database",
    "build_container",
    "check_engine",
    "load_check_catalog",
]


@dataclass(frozen=True, slots=True)
class Container:
    """Every adapter and use case of a process, wired once (composition root)."""

    settings: Settings
    engine: AsyncEngine
    tenant_access: TenantAccessService
    workspaces: Workspaces
    members: OrganizationMembers
    audit: AuditQueries
    api_keys: ApiKeys
    webhooks: WebhookEndpoints
    billing: BillingService
    test_gateway: TestGateway
    uploads: DocumentUploads
    autofix: Autofix
    questions: NormQuestions
    documents: DocumentQueries
    catalog: CatalogQuery
    corpus_sync: CorpusSync
    corpus_indexing: IndexCorpusEdition
    corpus: CorpusQueries
    norm_search: NormSearch
    checks: CheckService
    check_progress: RunProgress
    recheck: RecheckDocuments
    quality: QualityQueries
    benchmark: CheckBenchmark
    platform: PlatformTenantQueries
    verifier: TokenVerifier
    provisioning: IdentityProvisioning
    ai: AiAdapters
    health_checks: Sequence[HealthCheck]
    job_handlers: Mapping[str, JobHandler]
    relay: OutboxRelay | None
    close: Callable[[], Awaitable[None]]


def _corpus_sources(core: Core, catalog: YamlActCatalog) -> dict[str, CorpusSource]:
    return {
        "pravo_ips": PravoIpsSource(
            PravoIpsClient(core.http, PravoIpsConfig()), catalog, core.clock
        ),
        "snapshot": SnapshotSource(catalog),
    }


async def build_container(
    settings: Settings,
    publisher: JobPublisher | None = None,
    overrides: Overrides | None = None,
) -> Container:
    core = await build_core(settings, overrides or Overrides())
    uow, clock = core.uow, core.clock
    checks = build_checks(core)
    acts = YamlActCatalog(settings.corpus_catalog)
    corpus_indexing = IndexCorpusEdition(uow, core.embedder, clock)
    limits = UploadLimits(max_bytes=settings.max_upload_bytes)
    uploads = DocumentUploads(
        uow,
        core.blobs,
        SUPPORTED_FORMATS,
        DOCUMENT_KINDS,
        clock,
        limits,
        core.gate,
        core.audit,
        core.events,
    )
    payments = TestPaymentProvider(
        settings.payments.test_secret.get_secret_value(), settings.web_url
    )
    transport = core.overrides.webhook_transport or HttpWebhookTransport(
        core.http, allow_private=settings.integrations.webhooks_allow_private
    )

    async def close() -> None:
        await checks.feed.close()
        await core.close()

    return Container(
        settings=settings,
        engine=core.engine,
        tenant_access=TenantAccessService(
            uow,
            core.directory,
            AccessPolicy(ORGANIZATION_ROLES, PLATFORM_ROLES),
            clock,
            DefaultWorkspace(
                slug=settings.tenancy.default_workspace_slug,
                name=settings.tenancy.default_workspace_name,
            ),
        ),
        workspaces=Workspaces(uow, core.gate, ORGANIZATION_ROLES, core.audit, clock),
        members=OrganizationMembers(
            uow, core.directory, core.administration, ORGANIZATION_ROLES, core.audit, core.meter
        ),
        audit=AuditQueries(uow),
        api_keys=ApiKeys(uow, core.audit, clock),
        webhooks=WebhookEndpoints(
            uow,
            core.events,
            core.audit,
            clock,
            allow_http=settings.integrations.webhooks_allow_private,
        ),
        billing=BillingService(
            uow, core.plans, core.meter, payments, core.audit, clock, web_url=settings.web_url
        ),
        test_gateway=TestGateway(payments, uow, clock),
        uploads=uploads,
        questions=NormQuestions(
            uow,
            checks.norms,
            core.embedder,
            core.language_model,
            core.meter,
            clock,
            configured=core.ai.configured or core.overrides.language_model is not None,
        ),
        autofix=Autofix(
            uow,
            core.blobs,
            uploads,
            DocxPatcher(),
            checks.catalog,
            core.gate,
            core.meter,
            core.audit,
        ),
        documents=DocumentQueries(uow, core.blobs, DOCUMENT_KINDS, RequisiteDetector(), core.gate),
        catalog=CatalogQuery(DOCUMENT_KINDS, SUPPORTED_FORMATS, limits),
        corpus_sync=CorpusSync(uow, acts, _corpus_sources(core, acts), clock),
        corpus_indexing=corpus_indexing,
        corpus=CorpusQueries(uow),
        norm_search=NormSearch(uow, core.embedder),
        checks=checks.service,
        check_progress=checks.progress,
        recheck=checks.recheck,
        quality=checks.quality,
        benchmark=checks.benchmark,
        platform=PlatformTenantQueries(uow),
        verifier=core.verifier,
        provisioning=core.keycloak,
        ai=core.ai,
        health_checks=(DatabaseHealth(core.engine), StorageHealth(core.blobs)),
        job_handlers={
            PARSE_DOCUMENT_VERSION.name: ParseDocumentVersion(
                uow,
                core.blobs,
                core.parsers,
                clock,
                follow_up=FollowUps(checks.scheduler, core.follow_ups),
            ),
            INDEX_CORPUS_EDITION.name: corpus_indexing,
            RUN_CHECKS.name: checks.run_job,
            DELIVER_WEBHOOK.name: DeliverWebhook(uow, transport, clock),
            NOTIFY_TEST_PAYMENT.name: TestPaymentNotifier(
                core.http, f"{settings.api_url}/api/v1/billing/webhooks/test"
            ),
        },
        relay=OutboxRelay(uow, publisher, clock) if publisher is not None else None,
        close=close,
    )
