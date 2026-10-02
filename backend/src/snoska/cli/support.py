from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.bootstrap.container import Container, build_container
from snoska.bootstrap.settings import Settings
from snoska.infrastructure.observability.logging import configure_logging
from snoska.infrastructure.persistence.database import DatabaseConfig, create_engine


def settings_for_cli() -> Settings:
    settings = Settings()
    configure_logging(settings.observability.log_level, json=False)
    return settings


@asynccontextmanager
async def container_scope(settings: Settings) -> AsyncIterator[Container]:
    container = await build_container(settings)
    try:
        yield container
    finally:
        await container.close()


def owner_engine(settings: Settings) -> AsyncEngine:
    """An engine as the schema owner, for commands that change the schema."""
    db = settings.database
    return create_engine(
        DatabaseConfig(
            host=db.host,
            port=db.port,
            name=db.name,
            user=db.owner_user,
            password=db.owner_password.get_secret_value(),
            pool_size=1,
            max_overflow=0,
            statement_timeout_ms=0,
        )
    )
