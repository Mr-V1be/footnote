from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

JobPayload = Mapping[str, str]
JobHandler = Callable[[JobPayload], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class JobSpec:
    """A kind of background work: where it runs and how it is retried."""

    name: str
    queue: str
    max_retries: int
    time_limit_seconds: int
    min_backoff_ms: int = 2_000
    max_backoff_ms: int = 300_000


class JobPublisher(Protocol):
    def publish(self, job_name: str, payload: JobPayload) -> None:
        """Hand a job to the queue. Must raise if the broker did not accept it."""
        ...
