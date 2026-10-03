from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Email:
    to: tuple[str, ...]
    subject: str
    text: str


class Mailer(Protocol):
    async def send(self, email: Email) -> None:
        """Deliver to the mail server; raise on failure (the job is retried)."""
        ...


class PlatformAdmins(Protocol):
    """Who operates the platform and gets its notices."""

    async def emails(self) -> Sequence[str]: ...
