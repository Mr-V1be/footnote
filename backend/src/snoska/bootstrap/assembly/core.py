from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.application.audit.trail import AuditTrail
from snoska.application.billing.meter import UsageMeter
from snoska.application.integrations.events import EventFollowUps, OrganizationEvents
from snoska.application.tenancy.gate import WorkspaceGate
from snoska.bootstrap.providers import AiAdapters, build_ai_adapters
from snoska.bootstrap.settings import Settings
from snoska.bootstrap.storage import build_blob_storage
from snoska.domain.billing.plans import PlanCatalog
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES
from snoska.infrastructure.billing.plans import load_plans
from snoska.infrastructure.identity.claims import KeycloakClaimsMapper
from snoska.infrastructure.identity.jwks import JwksKeySource
from snoska.infrastructure.identity.jwt_verifier import JwtTokenVerifier, KeySource, TokenPolicy
from snoska.infrastructure.identity.keycloak_admin import KeycloakAdminClient, KeycloakAdminConfig
from snoska.infrastructure.integrations.secret_box import FernetSecretBox
from snoska.infrastructure.parsing.docx.parser import DocxParser
from snoska.infrastructure.parsing.ocr.tesseract import TesseractConfig, TesseractOcrEngine
from snoska.infrastructure.parsing.pdf.parser import PdfLimits, PdfParser
from snoska.infrastructure.parsing.registry import ParserRegistry
from snoska.infrastructure.persistence.database import DatabaseConfig, create_engine
from snoska.infrastructure.persistence.unit_of_work import SqlUnitOfWorkFactory
from snoska.infrastructure.system.clock import SystemClock
from snoska.ports.ai import Embedder, LanguageModel
from snoska.ports.blob_storage import BlobStorage
from snoska.ports.identity import MemberAdministration, OrganizationDirectory, TokenVerifier
from snoska.ports.integrations.transport import WebhookTransport

HTTP_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class Overrides:
    """Adapters replaced in tests where the real provider is not available."""

    key_source: KeySource | None = None
    directory: OrganizationDirectory | None = None
    administration: MemberAdministration | None = None
    embedder: Embedder | None = None
    language_model: LanguageModel | None = None
    webhook_transport: WebhookTransport | None = None


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


@dataclass(slots=True)
class Core:
    """Adapters and services every part of the application shares."""

    settings: Settings
    overrides: Overrides
    engine: AsyncEngine
    http: httpx.AsyncClient
    ai: AiAdapters
    clock: SystemClock
    uow: SqlUnitOfWorkFactory
    blobs: BlobStorage
    keycloak: KeycloakAdminClient
    verifier: TokenVerifier
    parsers: ParserRegistry
    plans: PlanCatalog
    gate: WorkspaceGate = field(init=False)
    audit: AuditTrail = field(init=False)
    events: OrganizationEvents = field(init=False)
    follow_ups: EventFollowUps = field(init=False)
    meter: UsageMeter = field(init=False)

    def __post_init__(self) -> None:
        self.gate = WorkspaceGate(ORGANIZATION_ROLES)
        self.audit = AuditTrail(self.clock)
        self.events = OrganizationEvents(self.clock)
        self.follow_ups = EventFollowUps(self.events)
        self.meter = UsageMeter(self.plans, self.clock)

    @property
    def directory(self) -> OrganizationDirectory:
        return self.overrides.directory or self.keycloak

    @property
    def administration(self) -> MemberAdministration:
        return self.overrides.administration or self.keycloak

    @property
    def embedder(self) -> Embedder:
        return self.overrides.embedder or self.ai.embedder

    @property
    def language_model(self) -> LanguageModel:
        return self.overrides.language_model or self.ai.language_model

    async def close(self) -> None:
        await self.ai.close()
        await self.http.aclose()
        await self.engine.dispose()


async def build_core(settings: Settings, overrides: Overrides) -> Core:
    engine = create_engine(app_database(settings))
    http = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    try:
        ai = build_ai_adapters(settings.ai)
    except BaseException:
        await http.aclose()
        await engine.dispose()
        raise
    clock = SystemClock()
    box = FernetSecretBox(settings.integrations.secrets_key.get_secret_value())
    return Core(
        settings=settings,
        overrides=overrides,
        engine=engine,
        http=http,
        ai=ai,
        clock=clock,
        uow=SqlUnitOfWorkFactory(engine, box),
        blobs=build_blob_storage(settings.storage),
        keycloak=KeycloakAdminClient(
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
        ),
        verifier=JwtTokenVerifier(
            overrides.key_source or JwksKeySource(http, settings.keycloak.jwks_url),
            TokenPolicy(issuer=settings.keycloak.issuer, audience=settings.keycloak.api_client_id),
            KeycloakClaimsMapper(settings.keycloak.api_client_id),
        ),
        parsers=ParserRegistry(
            [DocxParser(), PdfParser(TesseractOcrEngine(TesseractConfig()), PdfLimits())]
        ),
        plans=load_plans(settings.billing.plans),
    )
