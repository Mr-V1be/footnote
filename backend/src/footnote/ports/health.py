from __future__ import annotations

from typing import Protocol


class HealthCheck(Protocol):
    name: str

    async def check(self) -> bool:
        """True when the dependency answers; must not raise."""
        ...
