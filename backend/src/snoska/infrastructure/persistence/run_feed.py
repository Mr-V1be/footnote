from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from snoska.infrastructure.persistence.database import DatabaseConfig
from snoska.infrastructure.persistence.tables.checks import CHECK_RUNS_CHANNEL
from snoska.ports.checks.events import RunChanged

log = structlog.get_logger(__name__)

# A subscriber that does not keep up loses the oldest changes, never blocks
# the others; it re-reads the run anyway, so only intermediate counts are lost.
QUEUE_SIZE = 64


class _QueueChanges:
    def __init__(self, queue: asyncio.Queue[RunChanged]) -> None:
        self._queue = queue

    async def next(self, within_seconds: float) -> RunChanged | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=within_seconds)
        except TimeoutError:
            return None


class PgRunChangeFeed:
    """Run changes from the database's notifications, shared by a process.

    One connection listens for every subscriber of the process; the trigger on
    ``check_runs`` sends the run and its tenant. Any number of API instances
    can each run a feed: every one of them receives every notification.
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._connection: asyncpg.Connection | None = None
        self._subscribers: set[asyncio.Queue[RunChanged]] = set()
        self._lock = asyncio.Lock()

    def _on_notify(self, _connection: Any, _pid: int, _channel: str, payload: str) -> None:
        try:
            data = json.loads(payload)
            change = RunChanged(
                organization_id=UUID(data["organization_id"]), run_id=UUID(data["run_id"])
            )
        except (ValueError, KeyError, TypeError):
            log.warning("checks.feed_bad_payload", payload=payload[:200])
            return
        for queue in self._subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(change)

    async def _ensure_listening(self) -> None:
        async with self._lock:
            if self._connection is not None and not self._connection.is_closed():
                return
            self._connection = await asyncpg.connect(
                host=self._config.host,
                port=self._config.port,
                user=self._config.user,
                password=self._config.password,
                database=self._config.name,
            )
            await self._connection.add_listener(CHECK_RUNS_CHANNEL, self._on_notify)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[_QueueChanges]:
        await self._ensure_listening()
        queue: asyncio.Queue[RunChanged] = asyncio.Queue(QUEUE_SIZE)
        self._subscribers.add(queue)
        try:
            yield _QueueChanges(queue)
        finally:
            self._subscribers.discard(queue)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
