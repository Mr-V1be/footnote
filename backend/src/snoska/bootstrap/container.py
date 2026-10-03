from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.application.audit.queries import AuditQueries
from snoska.application.audit.trail import AuditTrail
from snoska.application.checks.deterministic import DeterministicExecutor
from snoska.application.checks.engine import CheckEngine
from snoska.application.checks.job import RunChecks
from snoska.application.checks.legal.executor import LegalCheckSettings, LegalExecutor
from snoska.application.checks.norms import NormLibrary
from snoska.application.checks.progress import RunProgress
from snoska.application.checks.quality.benchmark import CheckBenchmark
from snoska.application.checks.quality.queries import QualityQueries
from snoska.application.checks.recheck import RecheckDocuments
from snoska.application.checks.scheduling import CheckScheduler
from snoska.application.checks.service import CheckService
from snoska.application.corpus.indexing import IndexCorpusEdition
from snoska.application.corpus.queries import CorpusQueries
from snoska.application.corpus.search import NormSearch
from snoska.application.corpus.sync import CorpusSync
from snoska.application.documents.catalog import CatalogQuery
from snoska.application.documents.parsing import ParseDocumentVersion
from snoska.application.documents.queries import DocumentQueries
from snoska.application.documents.upload import DocumentUploads, UploadLimits
from snoska.application.shared.jobs import INDEX_CORPUS_EDITION, PARSE_DOCUMENT_VERSION, RUN_CHECKS
from snoska.application.shared.outbox_relay import OutboxRelay
from snoska.application.tenancy.access import DefaultWorkspace, TenantAccessService
from snoska.application.tenancy.gate import WorkspaceGate
from snoska.application.tenancy.members import OrganizationMembers
from snoska.application.tenancy.platform import PlatformTenantQueries
from snoska.application.tenancy.workspaces import Workspaces
from snoska.bootstrap.providers import AiAdapters, build_ai_adapters
from snoska.bootstrap.settings import ChecksSettings, Settings
from snoska.bootstrap.storage import build_blob_storage
from snoska.domain.checks.catalog import CheckCatalog, CheckMethod
from snoska.domain.checks.rules.registry import DEFAULT_RULES
from snoska.domain.documents.formats import SUPPORTED_FORMATS
from snoska.domain.documents.kinds import DOCUMENT_KINDS
from snoska.domain.documents.requisites import RequisiteDetector
from snoska.domain.tenancy.access import AccessPolicy
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES, PLATFORM_ROLES
from snoska.infrastructure.checks.catalog import YamlCheckCatalog
from snoska.infrastructure.checks.quality_store import JsonQualityReportStore
from snoska.infrastructure.checks.reference import YamlReferenceSet
from snoska.infrastructure.corpus_sources.catalog import YamlActCatalog
from snoska.infrastructure.corpus_sources.pravo_ips import (
    PravoIpsClient,
    PravoIpsConfig,
    PravoIpsSource,
)
from snoska.infrastructure.corpus_sources.snapshot import SnapshotSource
from snoska.infrastructure.identity.claims import KeycloakClaimsMapper
from snoska.infrastructure.identity.jwks import JwksKeySource
from snoska.infrastructure.identity.jwt_verifier import JwtTokenVerifier, KeySource, TokenPolicy
from snoska.infrastructure.identity.keycloak_admin import KeycloakAdminClient, KeycloakAdminConfig
from snoska.infrastructure.parsing.docx.parser import DocxParser
from snoska.infrastructure.parsing.ocr.tesseract import TesseractConfig, TesseractOcrEngine
from snoska.infrastructure.parsing.pdf.parser import PdfLimits, PdfParser
from snoska.infrastructure.parsing.registry import ParserRegistry
from snoska.infrastructure.persistence.database import DatabaseConfig, create_engine
from snoska.infrastructure.persistence.health import DatabaseHealth
from snoska.infrastructure.persistence.run_feed import PgRunChangeFeed
from snoska.infrastructure.persistence.unit_of_work import SqlUnitOfWorkFactory
from snoska.infrastructure.storage.health import StorageHealth
from snoska.infrastructure.system.clock import SystemClock
from snoska.ports.ai import Embedder, LanguageModel
from snoska.ports.corpus_source import CorpusSource
from snoska.ports.health import HealthCheck
from snoska.ports.identity import (
    IdentityProvisioning,
    MemberAdministration,
    OrganizationDirectory,
    TokenVerifier,
)
from snoska.ports.jobs import JobHandler, JobPublisher

HTTP_TIMEOUT_SECONDS = 30.0


def load_check_catalog(settings: ChecksSettings) -> CheckCatalog:
    return YamlCheckCatalog(settings.catalog_dir, DEFAULT_RULES, DOCUMENT_KINDS).load()


def check_engine(
    settings: ChecksSettings, embedder: Embedder, model: LanguageModel, norms: NormLibrary
) -> CheckEngine:
    return CheckEngine(
        {
            CheckMethod.DETERMINISTIC: DeterministicExecutor(DEFAULT_RULES),
            CheckMethod.MODEL: LegalExecutor(
                embedder,
                model,
                norms,
                LegalCheckSettings(
                    concurrency=settings.model_concurrency,
                    fragments=settings.fragments,
                    related_norms=settings.related_norms,
                    max_attempts=settings.max_attempts,
                ),
            ),
        }
    )


def app_database(settings: Settings) -> DatabaseConfig:
    db = settings.database
    return DatabaseConfig(
        host=db.host,
        port=db.port,
        name=db.name,
        user=db.app_user,
        password=db.app_password.get_secret_value(),
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        statement_timeout_ms=db.statement_timeout_ms,
    )


@dataclass(frozen=True, slots=True)
class Overrides:
    """Adapters replaced in tests where the real provider is not available."""

    key_source: KeySource | None = None
    directory: OrganizationDirectory | None = None
    administration: MemberAdministration | None = None
    embedder: Embedder | None = None
    language_model: LanguageModel | None = None


@dataclass(frozen=True, slots=True)
class Container:
    """Every adapter and use case of a process, wired once (composition root)."""

    settings: Settings
    engine: AsyncEngine
    tenant_access: TenantAccessService
    workspaces: Workspaces
    members: OrganizationMembers
    audit: AuditQueries
    uploads: DocumentUploads
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


async def build_container(
    settings: Settings,
    publisher: JobPublisher | None = None,
    overrides: Overrides | None = None,
) -> Container:
    overrides = overrides or Overrides()
    engine = create_engine(app_database(settings))
    http = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    try:
        ai = build_ai_adapters(settings.ai)
    except BaseException:
        await http.aclose()
        await engine.dispose()
        raise

    clock = SystemClock()
    uow = SqlUnitOfWorkFactory(engine)
    blobs = build_blob_storage(settings.storage)
    directory = KeycloakAdminClient(
        http,
        KeycloakAdminConfig(
            base_url=settings.keycloak.url,
            realm=settings.keycloak.realm,
            client_id=settings.directory.client_id,
            client_secret=settings.directory.client_secret.get_secret_value(),
            api_client_id=settings.keycloak.api_client_id,
            web_client_id=settings.keycloak.web_client_id,
            web_url=settings.web_url,
        ),
    )
    verifier = JwtTokenVerifier(
        overrides.key_source or JwksKeySource(http, settings.keycloak.jwks_url),
        TokenPolicy(issuer=settings.keycloak.issuer, audience=settings.keycloak.api_client_id),
        KeycloakClaimsMapper(settings.keycloak.api_client_id),
    )
    catalog = YamlActCatalog(settings.corpus_catalog)
    sources: dict[str, CorpusSource] = {
        "pravo_ips": PravoIpsSource(PravoIpsClient(http, PravoIpsConfig()), catalog, clock),
        "snapshot": SnapshotSource(catalog),
    }
    parsers = ParserRegistry(
        [DocxParser(), PdfParser(TesseractOcrEngine(TesseractConfig()), PdfLimits())]
    )
    limits = UploadLimits(max_bytes=settings.max_upload_bytes)
    embedder = overrides.embedder or ai.embedder
    language_model = overrides.language_model or ai.language_model
    check_catalog = load_check_catalog(settings.checks)
    norms = NormLibrary(uow)
    gate = WorkspaceGate(ORGANIZATION_ROLES)
    audit = AuditTrail(clock)
    engine_of_checks = check_engine(settings.checks, embedder, language_model, norms)
    quality_store = JsonQualityReportStore(settings.checks.quality_report)
    scheduler = CheckScheduler(check_catalog, clock)
    run_feed = PgRunChangeFeed(app_database(settings))
    corpus_indexing = IndexCorpusEdition(uow, embedder, clock)

    async def close() -> None:
        await run_feed.close()
        await ai.close()
        await http.aclose()
        await engine.dispose()

    return Container(
        settings=settings,
        engine=engine,
        tenant_access=TenantAccessService(
            uow,
            overrides.directory or directory,
            AccessPolicy(ORGANIZATION_ROLES, PLATFORM_ROLES),
            clock,
            DefaultWorkspace(
                slug=settings.tenancy.default_workspace_slug,
                name=settings.tenancy.default_workspace_name,
            ),
        ),
        workspaces=Workspaces(uow, gate, ORGANIZATION_ROLES, audit, clock),
        members=OrganizationMembers(
            uow,
            overrides.directory or directory,
            overrides.administration or directory,
            ORGANIZATION_ROLES,
            audit,
        ),
        audit=AuditQueries(uow),
        uploads=DocumentUploads(
            uow, blobs, SUPPORTED_FORMATS, DOCUMENT_KINDS, clock, limits, gate, audit
        ),
        documents=DocumentQueries(uow, blobs, DOCUMENT_KINDS, RequisiteDetector(), gate),
        catalog=CatalogQuery(DOCUMENT_KINDS, SUPPORTED_FORMATS, limits),
        corpus_sync=CorpusSync(uow, catalog, sources, clock),
        corpus_indexing=corpus_indexing,
        corpus=CorpusQueries(uow),
        norm_search=NormSearch(uow, embedder),
        checks=CheckService(uow, check_catalog, scheduler, norms, clock, gate, audit),
        check_progress=RunProgress(uow, run_feed, gate),
        recheck=RecheckDocuments(uow, scheduler),
        quality=QualityQueries(quality_store, check_catalog),
        benchmark=CheckBenchmark(
            YamlReferenceSet(settings.checks.reference_dir, SUPPORTED_FORMATS),
            parsers,
            check_catalog,
            engine_of_checks,
            RequisiteDetector(),
            quality_store,
            clock,
            language_model.model or None,
        ),
        platform=PlatformTenantQueries(uow),
        verifier=verifier,
        provisioning=directory,
        ai=ai,
        health_checks=(DatabaseHealth(engine), StorageHealth(blobs)),
        job_handlers={
            PARSE_DOCUMENT_VERSION.name: ParseDocumentVersion(
                uow, blobs, parsers, clock, follow_up=scheduler
            ),
            INDEX_CORPUS_EDITION.name: corpus_indexing,
            RUN_CHECKS.name: RunChecks(
                uow,
                check_catalog,
                engine_of_checks,
                RequisiteDetector(),
                clock,
                language_model.model,
            ),
        },
        relay=OutboxRelay(uow, publisher, clock) if publisher is not None else None,
        close=close,
    )
