from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from footnote.cli.demo_reset import next_reset

MOSCOW = ZoneInfo("Europe/Moscow")


def test_the_reset_is_tonight_before_the_hour_and_tomorrow_after_it() -> None:
    evening = datetime(2026, 10, 3, 22, 15, tzinfo=MOSCOW)
    assert next_reset(evening, 3) == datetime(2026, 10, 4, 3, 0, tzinfo=MOSCOW)
    small_hours = datetime(2026, 10, 4, 1, 0, tzinfo=MOSCOW)
    assert next_reset(small_hours, 3) == datetime(2026, 10, 4, 3, 0, tzinfo=MOSCOW)
    on_the_hour = datetime(2026, 10, 4, 3, 0, tzinfo=MOSCOW)
    assert next_reset(on_the_hour, 3) == datetime(2026, 10, 5, 3, 0, tzinfo=MOSCOW)
