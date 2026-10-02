from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware.asyncio import AsyncIO

from snoska.infrastructure.observability.metrics import Metrics
from snoska.ports.jobs import JobHandler, JobPayload, JobSpec

MS_PER_SECOND = 1000


def create_broker(redis_url: str, namespace: str) -> RedisBroker:
    # The broker constructor carries no annotations in the library.
    broker = RedisBroker(url=redis_url, namespace=namespace)  # type: ignore[no-untyped-call]
    broker.add_middleware(AsyncIO())
    return broker


class DramatiqJobPublisher:
    """Publishes jobs by name; the worker side declares the matching actors."""

    def __init__(self, broker: RedisBroker, specs: Sequence[JobSpec]) -> None:
        self._broker = broker
        self._specs = {spec.name: spec for spec in specs}

    def publish(self, job_name: str, payload: JobPayload) -> None:
        spec = self._specs.get(job_name)
        if spec is None:
            raise LookupError(f"unknown job {job_name!r}")
        message: dramatiq.Message[Any] = dramatiq.Message(
            queue_name=spec.queue,
            actor_name=spec.name,
            args=(dict(payload),),
            kwargs={},
            options={},
        )
        self._broker.enqueue(message)


def declare_actors(
    broker: RedisBroker,
    specs: Sequence[JobSpec],
    handlers: Callable[[], Mapping[str, JobHandler]],
    metrics: Metrics,
) -> None:
    """Declares one actor per job spec.

    ``handlers`` is resolved lazily on first use, inside the worker's event
    loop, so database pools and HTTP clients bind to the loop that runs them.
    """
    for spec in specs:

        def bind(job_name: str) -> Callable[[dict[str, str]], Any]:
            async def run(payload: dict[str, str]) -> None:
                started = time.perf_counter()
                outcome = "failed"
                try:
                    await handlers()[job_name](payload)
                    outcome = "succeeded"
                finally:
                    metrics.jobs.labels(job_name, outcome).inc()
                    metrics.job_duration.labels(job_name).observe(time.perf_counter() - started)

            run.__name__ = job_name.replace(".", "_")
            return run

        declare = dramatiq.actor(
            actor_name=spec.name,
            queue_name=spec.queue,
            broker=broker,
            max_retries=spec.max_retries,
            time_limit=spec.time_limit_seconds * MS_PER_SECOND,
            min_backoff=spec.min_backoff_ms,
            max_backoff=spec.max_backoff_ms,
        )
        declare(bind(spec.name))
