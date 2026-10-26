from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    pool_size: int = 5
    max_overflow: int = 5
    statement_timeout_ms: int = 30_000

    def url(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        )


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    # Vectors travel in pgvector's text form through the SQLAlchemy type, so
    # no driver-level codec is registered.
    return create_async_engine(
        config.url(),
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "statement_timeout": str(config.statement_timeout_ms),
                "application_name": "snoska",
            }
        },
    )
