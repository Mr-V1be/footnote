"""The pace and the daily allowance of model requests, shared through Redis
by every process of the installation (the API answers questions, the worker
runs checks, the CLI runs the benchmark)."""

from __future__ import annotations

import time

import anyio
import structlog
from redis.asyncio import Redis

from footnote.ports.ai import ModelBudgetExhaustedError
from footnote.ports.clock import Clock

log = structlog.get_logger(__name__)

SECONDS_PER_MINUTE = 60
DAY_KEY_TTL_SECONDS = 2 * 24 * 60 * 60
MINUTE_KEY_TTL_SECONDS = 2 * SECONDS_PER_MINUTE
# A request never waits for the pace longer than this; it then goes ahead.
MAX_PACE_WAIT_SECONDS = 5 * SECONDS_PER_MINUTE


class UnlimitedBudget:
    """No allowance and no pace: a paid model or a server of one's own."""

    async def spend(self) -> None:
        return None

    async def refund(self) -> None:
        return None

    async def remaining_today(self) -> int | None:
        return None


class RedisRequestBudget:
    """Counts requests per UTC day (providers renew free allowances at UTC
    midnight) and per minute. A request over the day's allowance is refused
    and not counted; one over the minute's pace waits for the next minute."""

    def __init__(self, redis: Redis, *, per_minute: int, per_day: int, clock: Clock) -> None:
        self._redis = redis
        self._per_minute = per_minute
        self._per_day = per_day
        self._clock = clock

    def _day_key(self) -> str:
        return f"footnote:ai:requests:day:{self._clock.now().date().isoformat()}"

    async def spend(self) -> None:
        if self._per_day > 0:
            key = self._day_key()
            count = int(await self._redis.incr(key))
            if count == 1:
                await self._redis.expire(key, DAY_KEY_TTL_SECONDS)
            if count > self._per_day:
                await self._redis.decr(key)
                raise ModelBudgetExhaustedError(
                    f"the model allows {self._per_day} requests a day; today's are spent"
                )
        if self._per_minute > 0:
            await self._pace()

    async def refund(self) -> None:
        if self._per_day <= 0:
            return
        key = self._day_key()
        if int(await self._redis.decr(key)) < 0:
            await self._redis.set(key, 0, ex=DAY_KEY_TTL_SECONDS)

    async def _pace(self) -> None:
        waited = 0.0
        while True:
            minute = int(time.time() // SECONDS_PER_MINUTE)
            key = f"footnote:ai:requests:minute:{minute}"
            count = int(await self._redis.incr(key))
            if count == 1:
                await self._redis.expire(key, MINUTE_KEY_TTL_SECONDS)
            if count <= self._per_minute or waited >= MAX_PACE_WAIT_SECONDS:
                return
            await self._redis.decr(key)
            pause = (minute + 1) * SECONDS_PER_MINUTE - time.time() + 0.2
            log.info("ai.pace_wait", seconds=round(pause, 1))
            await anyio.sleep(max(pause, 0.2))
            waited += pause

    async def remaining_today(self) -> int | None:
        if self._per_day <= 0:
            return None
        used = await self._redis.get(self._day_key())
        return max(self._per_day - int(used or 0), 0)
