from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from footnote.infrastructure.persistence.database import DatabaseConfig


class ChannelListener:
    """Wakes an event whenever the database sends a notification on a channel."""

    def __init__(self, config: DatabaseConfig, channel: str) -> None:
        self._config = config
        self._channel = channel
        self._connection: asyncpg.Connection | None = None
        self.event = asyncio.Event()

    def _on_notify(self, *_args: Any) -> None:
        self.event.set()

    async def start(self) -> None:
        self._connection = await asyncpg.connect(
            host=self._config.host,
            port=self._config.port,
            user=self._config.user,
            password=self._config.password,
            database=self._config.name,
        )
        await self._connection.add_listener(self._channel, self._on_notify)

    async def stop(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
