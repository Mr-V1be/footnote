from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from snoska.infrastructure.observability.tracing import TracingExporter

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "backend"
ENV_FILE = REPO_ROOT / ".env"
BYTES_PER_MEGABYTE = 1024 * 1024


def _config(prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix, env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )


class DatabaseSettings(BaseSettings):
    model_config = _config("SNOSKA_DB_")

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
    model_config = _config("SNOSKA_REDIS_")

    host: str = "127.0.0.1"
    port: int = 46311
    password: SecretStr = SecretStr("")
    database: int = 0

    def url(self) -> str:
        secret = quote(self.password.get_secret_value(), safe="")
        auth = f":{secret}@" if secret else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.database}"


class KeycloakSettings(BaseSettings):
    model_config = _config("SNOSKA_KEYCLOAK_")

    # Public base URL: it is the token issuer the browser and the API agree on.
    url: str = "http://localhost:46320"
    realm: str = "snoska"
    api_client_id: str = "snoska-api"

    @property
    def issuer(self) -> str:
        return f"{self.url}/realms/{self.realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/certs"


class DirectorySettings(BaseSettings):
    model_config = _config("SNOSKA_DIRECTORY_")

    client_id: str = "snoska-directory"
    client_secret: SecretStr = SecretStr("")


class AiProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"


class AiSettings(BaseSettings):
    model_config = _config("SNOSKA_")

    ai_provider: AiProvider = AiProvider.OLLAMA
    ollama_url: str = "http://127.0.0.1:46340"
    llm_model: str = "qwen3.5:9b"
    embedding_model: str = "bge-m3:567m"
    embedding_space: str = "bge-m3"
    openai_base_url: str = ""
    openai_api_key: SecretStr = SecretStr("")
    request_timeout_seconds: float = 180.0


class ApiSettings(BaseSettings):
    model_config = _config("SNOSKA_API_")

    host: str = "127.0.0.1"
    port: int = 46301
    max_upload_mb: int = 25


class WorkerSettings(BaseSettings):
    model_config = _config("SNOSKA_WORKER_")

    threads: int = 2
    metrics_port: int = 46302
    relay_poll_seconds: float = 5.0
    queue_namespace: str = "snoska"


class ObservabilitySettings(BaseSettings):
    model_config = _config("SNOSKA_")

    log_level: str = "INFO"
    log_json: bool = True
    tracing_exporter: TracingExporter = TracingExporter.NONE
    otlp_endpoint: str | None = None


class StorageSettings(BaseSettings):
    model_config = _config("SNOSKA_")

    storage_root: Path = Path("var/blobs")

    @property
    def blob_root(self) -> Path:
        root = self.storage_root
        return root if root.is_absolute() else REPO_ROOT / root


class TenancySettings(BaseSettings):
    model_config = _config("SNOSKA_TENANCY_")

    default_workspace_slug: str = "main"
    default_workspace_name: str = "Основное пространство"


class Settings(BaseSettings):
    """All configuration of a process. Values come from the environment / .env."""

    model_config = _config("SNOSKA_")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    keycloak: KeycloakSettings = Field(default_factory=KeycloakSettings)
    directory: DirectorySettings = Field(default_factory=DirectorySettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    tenancy: TenancySettings = Field(default_factory=TenancySettings)
    corpus_catalog: Path = BACKEND_ROOT / "data" / "corpus" / "acts.yaml"
    demo_root: Path = BACKEND_ROOT / "demo"

    @property
    def max_upload_bytes(self) -> int:
        return self.api.max_upload_mb * BYTES_PER_MEGABYTE
