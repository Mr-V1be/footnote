from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from footnote.domain.corpus.embedding import EmbeddingSpace
from footnote.infrastructure.observability.tracing import TracingExporter

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "backend"
ENV_FILE = REPO_ROOT / ".env"
BYTES_PER_MEGABYTE = 1024 * 1024


def _config(prefix: str) -> SettingsConfigDict:
    # Empty values in .env mean "not set": the default applies.
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )


class DatabaseSettings(BaseSettings):
    model_config = _config("FOOTNOTE_DB_")

    host: str = "127.0.0.1"
    port: int = 46310
    name: str = "snoska"
    app_user: str = "snoska_app"
    app_password: SecretStr = SecretStr("")
    owner_user: str = "snoska_owner"
    owner_password: SecretStr = SecretStr("")
    pool_size: int = 5
    max_overflow: int = 5
    statement_timeout_ms: int = 30_000


class RedisSettings(BaseSettings):
    model_config = _config("FOOTNOTE_REDIS_")

    host: str = "127.0.0.1"
    port: int = 46311
    password: SecretStr = SecretStr("")
    database: int = 0

    def url(self) -> str:
        secret = quote(self.password.get_secret_value(), safe="")
        auth = f":{secret}@" if secret else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.database}"


class KeycloakSettings(BaseSettings):
    model_config = _config("FOOTNOTE_KEYCLOAK_")

    # Public base URL: it is the token issuer the browser and the API agree on.
    url: str = "http://localhost:46320"
    # Where the servers themselves reach Keycloak, inside a private network
    # (production: http://keycloak:8080); the public URL when empty.
    internal_url: str = ""
    realm: str = "snoska"
    api_client_id: str = "snoska-api"
    # The web app's client: invitation links lead back to it.
    web_client_id: str = "snoska-web"

    @property
    def issuer(self) -> str:
        return f"{self.url}/realms/{self.realm}"

    @property
    def backchannel_url(self) -> str:
        return self.internal_url or self.url

    @property
    def jwks_url(self) -> str:
        return f"{self.backchannel_url}/realms/{self.realm}/protocol/openid-connect/certs"


class DirectorySettings(BaseSettings):
    model_config = _config("FOOTNOTE_DIRECTORY_")

    client_id: str = "snoska-directory"
    client_secret: SecretStr = SecretStr("")


class AiProvider(StrEnum):
    # No model API configured: model checks report "model not connected".
    NONE = "none"
    # Any server implementing the OpenAI chat completions and embeddings API.
    OPENAI_COMPATIBLE = "openai_compatible"


_SPACE_UNSAFE = re.compile(r"[^a-z0-9]+")
_SPACE_CODE_LIMIT = 40


class AiSettings(BaseSettings):
    """Models run only behind an external API; nothing runs on this machine."""

    model_config = _config("FOOTNOTE_")

    ai_provider: AiProvider = AiProvider.NONE
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    # Embeddings may come from another endpoint; empty values reuse the LLM's.
    embedding_base_url: str = ""
    embedding_api_key: SecretStr = SecretStr("")
    embedding_model: str = ""
    # Vector size the embedding model returns; it names the vector space.
    embedding_dimensions: int = 0
    request_timeout_seconds: float = 120.0
    # Models that answer when the first one is rate-limited, comma-separated.
    # Free models only, unless the owner decides otherwise.
    llm_fallback_models: str = ""
    # Extra fields of every chat request, as JSON (provider-specific options,
    # e.g. {"reasoning": {"effort": "low"}} for reasoning models).
    llm_extra_body: str = ""
    # The provider's pace and daily allowance (0: none), shared by all processes.
    llm_requests_per_minute: int = Field(default=0, ge=0)
    llm_requests_per_day: int = Field(default=0, ge=0)
    # A cached answer is reused for this many days.
    llm_cache_days: int = Field(default=30, ge=0)
    # Answer repeated requests from the cache. The benchmark turns reading
    # off to time the model itself; its answers are stored all the same.
    llm_cache_reads: bool = True

    def extra_body(self) -> dict[str, object]:
        if not self.llm_extra_body.strip():
            return {}
        value = json.loads(self.llm_extra_body)
        if not isinstance(value, dict):
            raise ValueError("FOOTNOTE_LLM_EXTRA_BODY must be a JSON object")
        return value

    def fallback_models(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.llm_fallback_models.split(",") if item.strip())

    def embedding_space(self) -> EmbeddingSpace:
        """The vector space of the configured model: vectors of different
        models or sizes are never compared, so each has its own space."""
        if not self.embedding_model or self.embedding_dimensions <= 0:
            return EmbeddingSpace(code=UNCONFIGURED_SPACE, dimensions=0)
        slug = _SPACE_UNSAFE.sub("-", self.embedding_model.lower()).strip("-")
        return EmbeddingSpace(
            code=f"{slug[:_SPACE_CODE_LIMIT]}-{self.embedding_dimensions}",
            dimensions=self.embedding_dimensions,
        )

    def require_api(self) -> None:
        missing = [
            name
            for name, value in (
                ("FOOTNOTE_LLM_BASE_URL", self.llm_base_url),
                ("FOOTNOTE_LLM_MODEL", self.llm_model),
                ("FOOTNOTE_EMBEDDING_MODEL", self.embedding_model),
            )
            if not value
        ]
        if self.embedding_dimensions <= 0:
            missing.append("FOOTNOTE_EMBEDDING_DIMENSIONS")
        if missing:
            raise ValueError(f"the openai_compatible provider needs {', '.join(missing)}")


UNCONFIGURED_SPACE = "none"


class ChecksSettings(BaseSettings):
    model_config = _config("FOOTNOTE_CHECKS_")

    catalog_dir: Path = BACKEND_ROOT / "data" / "checks"
    # Labelled documents the checks are measured on, and the latest result.
    reference_dir: Path = BACKEND_ROOT / "demo" / "reference"
    quality_report: Path = BACKEND_ROOT / "data" / "quality" / "benchmark.json"
    # Trials of candidate language models on the reference set.
    model_trials: Path = BACKEND_ROOT / "data" / "quality" / "models"
    # Requirements of a document asked in one model request: free tiers allow
    # few requests a day, so a document's legal checks share one or two.
    checks_per_request: int = 12
    # Passages of the document retrieved for one requirement.
    fragments: int = 4
    # Provisions found by meaning, besides those the check names.
    related_norms: int = 1
    # Requests for a batch: the first, then the rejected verdicts once more.
    max_attempts: int = 2


class ApiSettings(BaseSettings):
    model_config = _config("FOOTNOTE_API_")

    host: str = "127.0.0.1"
    port: int = 46301
    max_upload_mb: int = 25
    # Server processes: one serves about a hundred requests a second
    # (docs/performance.md); production runs one per CPU core it is given.
    workers: int = Field(default=1, ge=1)


class WorkerSettings(BaseSettings):
    model_config = _config("FOOTNOTE_WORKER_")

    threads: int = 2
    metrics_port: int = 46302
    relay_poll_seconds: float = 5.0
    queue_namespace: str = "snoska"


class ObservabilitySettings(BaseSettings):
    model_config = _config("FOOTNOTE_")

    log_level: str = "INFO"
    log_json: bool = True
    tracing_exporter: TracingExporter = TracingExporter.NONE
    otlp_endpoint: str | None = None


class StorageBackend(StrEnum):
    LOCAL = "local"
    S3 = "s3"


class StorageSettings(BaseSettings):
    """Where files are kept: a local directory or an S3-compatible store."""

    model_config = _config("FOOTNOTE_")

    storage_backend: StorageBackend = StorageBackend.LOCAL
    storage_root: Path = Path("var/blobs")
    s3_endpoint: str = "127.0.0.1:46340"
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_bucket: str = "snoska"
    s3_secure: bool = False
    s3_region: str | None = None

    @property
    def blob_root(self) -> Path:
        root = self.storage_root
        return root if root.is_absolute() else REPO_ROOT / root


class IntegrationsSettings(BaseSettings):
    model_config = _config("FOOTNOTE_")

    # Seals stored secrets (webhook signing keys); `make env` generates it.
    secrets_key: SecretStr = SecretStr("")
    # The demo stand delivers webhooks to its own receiver on loopback over
    # plain http; anywhere else endpoints are https and public.
    webhooks_allow_private: bool = False
    # Serves a receiver that accepts the stand's own signed webhooks.
    demo_receiver: bool = False


class PaymentsSettings(BaseSettings):
    model_config = _config("FOOTNOTE_PAYMENTS_")

    # Only the test provider exists until a live one is chosen and contracted.
    provider: str = "test"
    test_secret: SecretStr = SecretStr("")


class BillingSettings(BaseSettings):
    model_config = _config("FOOTNOTE_BILLING_")

    plans: Path = BACKEND_ROOT / "data" / "billing" / "plans.yaml"


class OperationsSettings(BaseSettings):
    model_config = _config("FOOTNOTE_")

    smtp_host: str = "127.0.0.1"
    smtp_port: int = 46331
    smtp_sender: str = "Сноска <no-reply@snoska.example>"
    # A real mail server asks for an account and STARTTLS; Mailpit does not.
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_start_tls: bool = False
    # How often the official portal is checked for new redactions.
    corpus_watch_interval_hours: int = 168
    # The realm role whose holders get the platform's notices.
    platform_admin_role: str = "platform-admin"


class DemoSettings(BaseSettings):
    """The demo stand: one-click sign-in by role, accounts that keep their
    roles and a nightly return to the seed. Off unless set: a production
    installation never enables it."""

    model_config = _config("FOOTNOTE_DEMO_")

    mode: bool = False
    # Local time of the nightly reset to the seed.
    reset_hour: int = Field(default=3, ge=0, le=23)
    timezone: str = "Europe/Moscow"


class TenancySettings(BaseSettings):
    model_config = _config("FOOTNOTE_TENANCY_")

    default_workspace_slug: str = "main"
    default_workspace_name: str = "Основное пространство"


class Settings(BaseSettings):
    """All configuration of a process. Values come from the environment / .env."""

    model_config = _config("FOOTNOTE_")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    keycloak: KeycloakSettings = Field(default_factory=KeycloakSettings)
    directory: DirectorySettings = Field(default_factory=DirectorySettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    checks: ChecksSettings = Field(default_factory=ChecksSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    tenancy: TenancySettings = Field(default_factory=TenancySettings)
    integrations: IntegrationsSettings = Field(default_factory=IntegrationsSettings)
    payments: PaymentsSettings = Field(default_factory=PaymentsSettings)
    billing: BillingSettings = Field(default_factory=BillingSettings)
    operations: OperationsSettings = Field(default_factory=OperationsSettings)
    demo: DemoSettings = Field(default_factory=DemoSettings)
    # Where people open the product (links in emails and invitations).
    web_url: str = "http://localhost:46300"
    # Where the API answers for calls made by the platform itself (webhooks
    # of the test payment provider).
    api_url: str = "http://127.0.0.1:46301"
    corpus_catalog: Path = BACKEND_ROOT / "data" / "corpus" / "acts.yaml"
    demo_root: Path = BACKEND_ROOT / "demo"

    @property
    def max_upload_bytes(self) -> int:
        return self.api.max_upload_mb * BYTES_PER_MEGABYTE
