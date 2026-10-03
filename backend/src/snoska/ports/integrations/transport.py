from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TransportResult:
    """What came back from an endpoint: a status code, or no answer at all."""

    status_code: int | None
    duration_ms: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300


class WebhookTransport(Protocol):
    async def post(self, url: str, body: bytes, headers: Mapping[str, str]) -> TransportResult:
        """Send once; never raises for network or HTTP failures."""
        ...


class SecretBox(Protocol):
    """Seals secrets the platform must read back (webhook signing keys)."""

    def seal(self, secret: str) -> str: ...

    def open(self, sealed: str) -> str: ...
