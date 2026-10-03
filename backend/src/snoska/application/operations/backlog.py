"""Waiting for the background work to finish (a refresh script's step)."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import anyio

from snoska.ports.operations.maintenance import Backlog, BacklogProbe


async def wait_until_idle(
    probe: BacklogProbe,
    *,
    timeout_seconds: float,
    poll_seconds: float = 2.0,
    sleep: Callable[[float], Awaitable[None]] = anyio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Backlog:
    """Polls until no work is left or the time is up; returns the last count.

    Idle must be seen twice in a row: a finished job may enqueue the next
    one (a parsed version queues its check) between two counts."""
    deadline = clock() + timeout_seconds
    quiet = 0
    while True:
        backlog = await probe.backlog()
        quiet = quiet + 1 if backlog.idle else 0
        if quiet >= 2 or clock() >= deadline:
            return backlog
        await sleep(poll_seconds)
