from __future__ import annotations

import asyncio
from datetime import timedelta

import structlog

from snoska.ports.clock import Clock
from snoska.ports.jobs import JobPublisher
from snoska.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)

RELAY_BATCH_SIZE = 100
RETRY_BASE_DELAY = timedelta(seconds=5)
RETRY_MAX_DELAY = timedelta(minutes=10)


class OutboxRelay:
    """Moves committed outbox messages to the job queue.

    Messages are claimed with row locks that skip rows held by other relay
    instances, so any number of relays can run side by side. Delivery is
    at-least-once; job handlers are idempotent.
    """

    def __init__(
        self, uow_factory: UnitOfWorkFactory, publisher: JobPublisher, clock: Clock
    ) -> None:
        self._uow_factory = uow_factory
        self._publisher = publisher
        self._clock = clock

    async def dispatch_due(self) -> int:
        dispatched = 0
        async with self._uow_factory.for_platform() as uow:
            messages = await uow.outbox.claim_due(self._clock.now(), RELAY_BATCH_SIZE)
            for message in messages:
                try:
                    self._publisher.publish(message.job_name, message.payload)
                except Exception as exc:  # broker outage: keep the message, retry later
                    delay = min(RETRY_BASE_DELAY * 2**message.attempts, RETRY_MAX_DELAY)
                    await uow.outbox.postpone(message.id, self._clock.now() + delay, repr(exc))
                    log.warning(
                        "outbox.publish_failed", message_id=str(message.id), error=repr(exc)
                    )
                    continue
                await uow.outbox.mark_dispatched(message.id, self._clock.now())
                dispatched += 1
            await uow.commit()
        return dispatched

    async def run(self, wake: asyncio.Event, stop: asyncio.Event, poll_interval: float) -> None:
        """Dispatch whenever woken (new rows) or every ``poll_interval`` seconds."""
        while not stop.is_set():
            try:
                while await self.dispatch_due() == RELAY_BATCH_SIZE:
                    pass
            except Exception:
                log.exception("outbox.relay_iteration_failed")
            wake.clear()
            waiters = {asyncio.ensure_future(wake.wait()), asyncio.ensure_future(stop.wait())}
            _, pending = await asyncio.wait(
                waiters, timeout=poll_interval, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
