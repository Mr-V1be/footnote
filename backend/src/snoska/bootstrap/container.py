from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.application.corpus.embedding import EmbedCorpusEdition
from snoska.application.corpus.queries import CorpusQueries
from snoska.application.corpus.search import NormSearch
from snoska.application.corpus.sync import CorpusSync
from snoska.application.documents.catalog import CatalogQuery
from snoska.application.documents.parsing import ParseDocumentVersion
from snoska.application.documents.queries import DocumentQueries
from snoska.application.documents.upload import DocumentUploads, UploadLimits
from snoska.application.shared.jobs import EMBED_CORPUS_EDITION, PARSE_DOCUMENT_VERSION
from snoska.application.shared.outbox_relay import OutboxRelay
from snoska.application.tenancy.access import DefaultWorkspace, TenantAccessService
from snoska.application.tenancy.platform import PlatformTenantQueries
from snoska.application.tenancy.workspaces import WorkspaceQueries
from snoska.bootstrap.providers import AiAdapters, build_ai_adapters
from snoska.bootstrap.settings import Settings
from snoska.domain.documents.formats import SUPPORTED_FORMATS
from snoska.domain.documents.kinds import DOCUMENT_KINDS
from snoska.domain.documents.requisites import RequisiteDetector
from snoska.domain.tenancy.access import AccessPolicy
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES, PLATFORM_ROLES
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
from snoska.infrastructure.persistence.embedding_spaces import load_embedding_space
from snoska.infrastructure.persistence.health import DatabaseHealth
from snoska.infrastructure.persistence.unit_of_work import SqlUnitOfWorkFactory
from snoska.infrastructure.storage.filesystem import FileSystemBlobStorage
from snoska.infrastructure.system.clock import SystemClock
from snoska.ports.ai import Embedder
from snoska.ports.corpus_source import CorpusSource
from snoska.ports.health import HealthCheck
from snoska.ports.identity import IdentityProvisioning, OrganizationDirectory, TokenVerifier
from snoska.ports.jobs import JobHandler, JobPublisher

HTTP_TIMEOUT_SECONDS = 30.0


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
    embedder: Embedder | None = None


@dataclass(frozen=True, slots=True)
class Container:
    """Every adapter and use case of a process, wired once (composition root)."""

    settings: Settings
    engine: AsyncEngine
    tenant_access: TenantAccessService
    workspaces: WorkspaceQueries
    uploads: DocumentUploads
    documents: DocumentQueries
    catalog: CatalogQuery
    corpus_sync: CorpusSync
    corpus: CorpusQueries
    norm_search: NormSearch
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
        space = await load_embedding_space(engine, settings.ai.embedding_space)
        ai = build_ai_adapters(settings.ai, space)
    except BaseException:
        await http.aclose()
        await engine.dispose()
        raise

    clock = SystemClock()
    uow = SqlUnitOfWorkFactory(engine)
    blobs = FileSystemBlobStorage(settings.storage.blob_root)
    directory = KeycloakAdminClient(
        http,
        KeycloakAdminConfig(
            base_url=settings.keycloak.url,
            realm=settings.keycloak.realm,
            client_id=settings.directory.client_id,
            client_secret=settings.directory.client_secret.get_secret_value(),
            api_client_id=settings.keycloak.api_client_id,
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

    async def close() -> None:
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
        workspaces=WorkspaceQueries(uow),
        uploads=DocumentUploads(uow, blobs, SUPPORTED_FORMATS, DOCUMENT_KINDS, clock, limits),
        documents=DocumentQueries(uow, blobs, DOCUMENT_KINDS, RequisiteDetector()),
        catalog=CatalogQuery(DOCUMENT_KINDS, SUPPORTED_FORMATS, limits),
        corpus_sync=CorpusSync(uow, catalog, sources, clock),
        corpus=CorpusQueries(uow),
        norm_search=NormSearch(uow, embedder),
        platform=PlatformTenantQueries(uow),
        verifier=verifier,
        provisioning=directory,
        ai=ai,
        health_checks=(DatabaseHealth(engine),),
        job_handlers={
            PARSE_DOCUMENT_VERSION.name: ParseDocumentVersion(uow, blobs, parsers, clock),
            EMBED_CORPUS_EDITION.name: EmbedCorpusEdition(uow, embedder, clock),
        },
        relay=OutboxRelay(uow, publisher, clock) if publisher is not None else None,
        close=close,
    )
