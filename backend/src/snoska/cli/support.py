from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from snoska.bootstrap.container import Container, build_container
from snoska.bootstrap.settings import Settings
from snoska.infrastructure.observability.logging import configure_logging


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
