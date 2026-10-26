from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from dramatiq.asyncio import get_event_loop_thread
from dramatiq.middleware import Middleware

Hook = Callable[[], Awaitable[None]]


def run_on_worker_loop(hook: Hook) -> None:
    """Run a coroutine on the worker's event loop and wait for it."""
    loop_thread = get_event_loop_thread()
    if loop_thread is None:
        raise RuntimeError("the worker event loop is not running")
    loop_thread.run_coroutine(hook())


class LoopStartup(Middleware):
    """Boot hook; register *after* AsyncIO so the loop already exists.

    Boot blocks until the hook finishes, so no message is consumed before the
    process is ready.
    """

    def __init__(self, hook: Hook) -> None:
        self._hook = hook

    def before_worker_boot(self, _broker: Any, _worker: Any) -> None:
        run_on_worker_loop(self._hook)


class LoopShutdown(Middleware):
    """Shutdown hook; register *before* AsyncIO so it runs while the loop is
    still alive, after every in-flight job has finished."""

    def __init__(self, hook: Hook) -> None:
        self._hook = hook

    def after_worker_shutdown(self, _broker: Any, _worker: Any) -> None:
        run_on_worker_loop(self._hook)
