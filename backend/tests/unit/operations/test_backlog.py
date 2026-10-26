"""A refresh waits until the background work is done, or gives up in time."""

from __future__ import annotations

from footnote.application.operations.backlog import wait_until_idle
from footnote.ports.operations.maintenance import Backlog

IDLE = Backlog(jobs=0, versions=0, checks=0)


class ScriptedProbe:
    def __init__(self, *counts: Backlog) -> None:
        self._counts = list(counts)
        self.calls = 0

    async def backlog(self) -> Backlog:
        self.calls += 1
        return self._counts.pop(0) if len(self._counts) > 1 else self._counts[0]


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


async def test_idle_must_hold_between_two_counts() -> None:
    # Between the parse and its check nothing is counted for a moment.
    probe = ScriptedProbe(
        Backlog(jobs=1, versions=1, checks=0), IDLE, Backlog(jobs=0, versions=0, checks=1), IDLE
    )
    fake = FakeTime()
    result = await wait_until_idle(
        probe, timeout_seconds=60, poll_seconds=1, sleep=fake.sleep, clock=fake.clock
    )
    assert result.idle
    assert probe.calls == 5


async def test_the_wait_ends_at_the_timeout_with_what_is_left() -> None:
    busy = Backlog(jobs=0, versions=0, checks=3)
    fake = FakeTime()
    result = await wait_until_idle(
        ScriptedProbe(busy), timeout_seconds=10, poll_seconds=2, sleep=fake.sleep, clock=fake.clock
    )
    assert result == busy
    assert fake.now >= 10
