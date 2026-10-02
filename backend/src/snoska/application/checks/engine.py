from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import structlog

from snoska.domain.checks.catalog import CheckDefinition, CheckMethod
from snoska.domain.checks.outcome import CheckOutcome
from snoska.domain.documents.structure import DocumentStructure
from snoska.ports.ai import AiProviderError, ModelNotConfiguredError
from snoska.ports.checks.embeddings import EmbeddingCache

log = structlog.get_logger(__name__)

MILLISECONDS = 1000


class CheckErrorCode:
    """Stable reasons a single check produced no verdict."""

    MODEL_NOT_CONFIGURED = "model_not_configured"
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID_MODEL_ANSWER = "invalid_model_answer"
    NORM_UNAVAILABLE = "norm_unavailable"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class DocumentUnderCheck:
    """A parsed document version as the checks see it (requisites detected).

    ``embeddings`` is where vectors of its passages are kept: the tenant's
    store in the database, or memory for a run outside it.
    """

    title: str
    kind: str
    structure: DocumentStructure
    embeddings: EmbeddingCache


class ExecutorSession(Protocol):
    """Checks of one method on one document, sharing what was prepared for it."""

    concurrency: int

    async def execute(self, check: CheckDefinition) -> CheckOutcome: ...


class CheckExecutor(Protocol):
    method: CheckMethod

    async def open(
        self, document: DocumentUnderCheck, checks: Sequence[CheckDefinition]
    ) -> ExecutorSession:
        """Prepare the shared context (e.g. a passage index); may raise AiProviderError."""
        ...


@dataclass(frozen=True, slots=True)
class Executed:
    check: CheckDefinition
    outcome: CheckOutcome
    duration_ms: int


Record = Callable[[Executed], Awaitable[None]]


def _provider_error_code(error: AiProviderError) -> str:
    if isinstance(error, ModelNotConfiguredError):
        return CheckErrorCode.MODEL_NOT_CONFIGURED
    return CheckErrorCode.MODEL_UNAVAILABLE


class _Unavailable:
    """Stands in for an executor that could not prepare: every check errs alike."""

    concurrency = 1

    def __init__(self, code: str) -> None:
        self._code = code

    async def execute(self, check: CheckDefinition) -> CheckOutcome:
        return CheckOutcome.failed(self._code)


class CheckEngine:
    """Runs checks on a document with the executor of each method.

    A failing check never stops the others: it is recorded with an error code
    and the run goes on. Results are recorded one at a time, in the order the
    checks finish, so the record callback never runs concurrently.
    """

    def __init__(self, executors: Mapping[CheckMethod, CheckExecutor]) -> None:
        self._executors = executors

    async def run(
        self, document: DocumentUnderCheck, checks: Sequence[CheckDefinition], record: Record
    ) -> None:
        lock = asyncio.Lock()
        tasks: list[Awaitable[None]] = []
        for method, executor in self._executors.items():
            group = [check for check in checks if check.method is method]
            if not group:
                continue
            session = await self._open(executor, document, group)
            limit = asyncio.Semaphore(max(1, session.concurrency))
            tasks.extend(self._execute(session, check, limit, lock, record) for check in group)
        await asyncio.gather(*tasks)

    @staticmethod
    async def _open(
        executor: CheckExecutor, document: DocumentUnderCheck, group: Sequence[CheckDefinition]
    ) -> ExecutorSession:
        try:
            return await executor.open(document, group)
        except AiProviderError as exc:
            log.warning("checks.executor_unavailable", method=executor.method, error=str(exc))
            return _Unavailable(_provider_error_code(exc))

    @staticmethod
    async def _execute(
        session: ExecutorSession,
        check: CheckDefinition,
        limit: asyncio.Semaphore,
        lock: asyncio.Lock,
        record: Record,
    ) -> None:
        async with limit:
            started = time.perf_counter()
            try:
                outcome = await session.execute(check)
            except AiProviderError as exc:
                log.warning("checks.model_unavailable", check=check.code, error=str(exc))
                outcome = CheckOutcome.failed(_provider_error_code(exc))
            except Exception:
                log.exception("checks.check_failed", check=check.code)
                outcome = CheckOutcome.failed(CheckErrorCode.INTERNAL_ERROR)
            duration = round((time.perf_counter() - started) * MILLISECONDS)
        async with lock:
            await record(Executed(check, outcome, duration))
