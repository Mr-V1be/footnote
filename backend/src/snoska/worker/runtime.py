from __future__ import annotations

import asyncio
import signal
import threading
from collections.abc import Mapping

import dramatiq
import structlog
from dramatiq.middleware.asyncio import AsyncIO
from prometheus_client import start_http_server

from snoska.application.shared.jobs import JOB_SPECS
from snoska.bootstrap.container import Container, app_database, build_container
from snoska.bootstrap.settings import Settings
from snoska.infrastructure.observability.metrics import Metrics
from snoska.infrastructure.persistence.notifications import ChannelListener
from snoska.infrastructure.persistence.tables.outbox import OUTBOX_CHANNEL
from snoska.infrastructure.queue.dramatiq_bus import (
    DramatiqJobPublisher,
    create_broker,
    declare_actors,
)
from snoska.infrastructure.queue.lifecycle import LoopShutdown, LoopStartup, run_on_worker_loop
from snoska.ports.jobs import JobHandler

log = structlog.get_logger(__name__)

SHUTDOWN_TIMEOUT_SECONDS = 30


class WorkerRuntime:
    """One worker process: queue consumers plus the outbox relay.

    Everything asynchronous (database pools, HTTP clients, the relay) lives on
    the single event loop the queue library runs async jobs on.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._metrics = Metrics()
        self._broker = create_broker(settings.redis.url(), settings.worker.queue_namespace)
        self._publisher = DramatiqJobPublisher(self._broker, JOB_SPECS)
        self._container: Container | None = None
        self._listener: ChannelListener | None = None
        self._relay_task: asyncio.Task[None] | None = None
        self._stop: asyncio.Event | None = None
        self._broker.add_middleware(LoopStartup(self._start), after=AsyncIO)
        self._broker.add_middleware(LoopShutdown(self._shutdown), before=AsyncIO)
        dramatiq.set_broker(self._broker)
        declare_actors(self._broker, JOB_SPECS, self._handlers, self._metrics)

    def _handlers(self) -> Mapping[str, JobHandler]:
        if self._container is None:
            raise RuntimeError("worker is not started")
        return self._container.job_handlers

    async def _start(self) -> None:
        self._container = await build_container(self._settings, self._publisher)
        self._listener = ChannelListener(app_database(self._settings), OUTBOX_CHANNEL)
        await self._listener.start()
        self._stop = asyncio.Event()
        relay = self._container.relay
        if relay is None:
            raise RuntimeError("worker container has no outbox relay")
        self._relay_task = asyncio.create_task(
            relay.run(self._listener.event, self._stop, self._settings.worker.relay_poll_seconds)
        )
        log.info("worker.started", threads=self._settings.worker.threads)

    async def _stop_relay(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if self._relay_task is not None:
            await self._relay_task

    async def _shutdown(self) -> None:
        if self._listener is not None:
            await self._listener.stop()
        if self._container is not None:
            await self._container.close()
        log.info("worker.stopped")

    def run(self) -> None:
        start_http_server(
            self._settings.worker.metrics_port, addr="127.0.0.1", registry=self._metrics.registry
        )
        worker = dramatiq.Worker(self._broker, worker_threads=self._settings.worker.threads)
        stopping = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stopping.set())
        worker.start()
        stopping.wait()
        log.info("worker.stopping")
        run_on_worker_loop(self._stop_relay)
        worker.stop(timeout=SHUTDOWN_TIMEOUT_SECONDS * 1000)
