from __future__ import annotations

from collections.abc import Sequence

import structlog

from footnote.domain.operations.schedule import PeriodicTask, TaskState
from footnote.domain.shared.ids import new_id
from footnote.ports.clock import Clock
from footnote.ports.outbox import OutboxMessage
from footnote.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)


class PeriodicScheduler:
    """Queues periodic tasks when they are due.

    Every worker ticks; the due rows are claimed with locks that skip rows
    held by another worker, so a task is queued once however many run.
    """

    def __init__(
        self, uow_factory: UnitOfWorkFactory, tasks: Sequence[PeriodicTask], clock: Clock
    ) -> None:
        self._uow_factory = uow_factory
        self._tasks = {task.name: task for task in tasks}
        self._clock = clock

    async def register(self) -> None:
        """New tasks run at the first tick, then every interval."""
        async with self._uow_factory.for_platform() as uow:
            for task in self._tasks.values():
                await uow.task_states.ensure(TaskState(task.name, next_run_at=self._clock.now()))
            await uow.commit()

    async def tick(self) -> int:
        now = self._clock.now()
        queued = 0
        async with self._uow_factory.for_platform() as uow:
            for state in await uow.task_states.claim_due(now, list(self._tasks)):
                task = self._tasks[state.name]
                await uow.outbox.add(
                    OutboxMessage(
                        id=new_id(),
                        job_name=task.job_name,
                        payload={"task": task.name},
                        created_at=now,
                    )
                )
                state.ran(now, task.interval)
                await uow.task_states.save(state)
                queued += 1
                log.info("scheduler.task_queued", task=task.name, next_run=state.next_run_at)
            await uow.commit()
        return queued

    async def run_now(self, name: str) -> None:
        """Queue a task at once (an operator's request), keeping its schedule."""
        task = self._tasks[name]
        async with self._uow_factory.for_platform() as uow:
            await uow.outbox.add(
                OutboxMessage(
                    id=new_id(),
                    job_name=task.job_name,
                    payload={"task": task.name},
                    created_at=self._clock.now(),
                )
            )
            await uow.commit()

    async def next_run(self, name: str) -> TaskState | None:
        async with self._uow_factory.for_platform() as uow:
            return await uow.task_states.get(name)
