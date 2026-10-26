from __future__ import annotations

import structlog
from redis.asyncio import Redis

log = structlog.get_logger(__name__)


class RedisHealth:
    """The job queue's broker answers."""

    name = "queue"

    def __init__(self, url: str) -> None:
        self._url = url

    async def check(self) -> bool:
        client: Redis = Redis.from_url(self._url, socket_timeout=2)
        try:
            return bool(await client.ping())
        except Exception as exc:  # any failure means "not available"
            log.warning("health.queue_unavailable", error=repr(exc))
            return False
        finally:
            await client.aclose()
