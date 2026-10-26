from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    invoice_id: UUID
    organization_id: UUID
    amount_kopecks: int
    currency: str
    description: str
    return_url: str


@dataclass(frozen=True, slots=True)
class PaymentSession:
    """A payment opened with the provider: its id and where to pay."""

    payment_id: str
    confirmation_url: str


class PaymentStatus(StrEnum):
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


@dataclass(frozen=True, slots=True)
class PaymentNotification:
    """A provider's notice about a payment, after its signature is verified."""

    event_id: str
    payment_id: str
    invoice_id: UUID
    organization_id: UUID
    status: PaymentStatus
    amount_kopecks: int


class InvalidNotificationError(Exception):
    """The notice is not signed by the provider or is malformed."""


class PaymentProvider(Protocol):
    """A payment service behind a port; the stand uses a test provider."""

    name: str

    async def open_payment(self, request: PaymentRequest) -> PaymentSession: ...

    def parse_notification(self, body: bytes, headers: dict[str, str]) -> PaymentNotification:
        """Verify and read a webhook; raise InvalidNotificationError."""
        ...
