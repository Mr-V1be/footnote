from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Email:
    to: tuple[str, ...]
    subject: str
    text: str


class Mailer(Protocol):
    async def send(self, email: Email) -> None:
        """Deliver to the mail server; raise on failure (the job is retried)."""
        ...


@dataclass(frozen=True, slots=True)
class Recipient:
    user_id: UUID
    email: str


class PlatformAdmins(Protocol):
    """Who operates the platform and gets its notices."""

    async def recipients(self) -> Sequence[Recipient]: ...
