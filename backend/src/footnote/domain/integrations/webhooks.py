from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from footnote.domain.shared.errors import ValidationError

URL_MAX_LENGTH = 2000
DESCRIPTION_MAX_LENGTH = 200
SECRET_BYTES = 24
SECRET_MARKER = "whsec_"  # noqa: S105 - a format marker, not a secret


class WebhookEvent(StrEnum):
    """Events an organization can subscribe an endpoint to."""

    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PARSED = "document.parsed"
    CHECK_COMPLETED = "check.completed"
    CHECK_FAILED = "check.failed"
    FINDING_REVIEWED = "finding.reviewed"
    # Sent on request to try an endpoint; nobody subscribes to it.
    PING = "ping"


SUBSCRIBABLE_EVENTS: tuple[WebhookEvent, ...] = tuple(
    event for event in WebhookEvent if event is not WebhookEvent.PING
)


class InvalidWebhookUrlError(ValidationError):
    code = "invalid_webhook_url"


def validate_url(url: str, *, allow_http: bool) -> str:
    """An absolute http(s) URL without credentials; plain http only when allowed."""
    value = url.strip()
    parts = urlsplit(value)
    allowed = {"https", "http"} if allow_http else {"https"}
    if (
        len(value) > URL_MAX_LENGTH
        or parts.scheme not in allowed
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise InvalidWebhookUrlError("the endpoint must be an https:// address")
    return value


def new_secret() -> str:
    return SECRET_MARKER + secrets.token_urlsafe(SECRET_BYTES)


def signature(secret: str, timestamp: int, body: bytes) -> str:
    """HMAC-SHA256 of "<timestamp>.<body>", hex: what a receiver recomputes."""
    message = str(timestamp).encode() + b"." + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def signature_header(secret: str, timestamp: int, body: bytes) -> str:
    return f"t={timestamp},v1={signature(secret, timestamp, body)}"


def verify_signature(secret: str, header: str, body: bytes) -> bool:
    fields = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    try:
        timestamp = int(fields["t"])
    except (KeyError, ValueError):
        return False
    return hmac.compare_digest(fields.get("v1", ""), signature(secret, timestamp, body))


@dataclass(slots=True)
class WebhookEndpoint:
    """Where an organization wants its events delivered, signed with a secret
    shown to the owner once (and on rotation)."""

    id: UUID
    organization_id: UUID
    url: str
    description: str
    events: frozenset[WebhookEvent]
    secret: str
    active: bool
    created_at: datetime

    def __post_init__(self) -> None:
        self.description = self.description.strip()
        if len(self.description) > DESCRIPTION_MAX_LENGTH:
            raise ValidationError("the description is too long")
        if not self.events or WebhookEvent.PING in self.events:
            raise ValidationError("an endpoint subscribes to at least one event")

    def wants(self, event: WebhookEvent) -> bool:
        return self.active and (event in self.events or event is WebhookEvent.PING)


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Exponential backoff: 30 s, 2 min, 8 min, 32 min, ~2 h; then give up."""

    max_attempts: int = 6
    first_delay: timedelta = timedelta(seconds=30)
    factor: int = 4
    max_delay: timedelta = timedelta(hours=3)

    def delay_after(self, attempts: int) -> timedelta:
        grown: timedelta = self.first_delay * self.factor ** max(attempts - 1, 0)
        return min(grown, self.max_delay)


@dataclass(slots=True)
class WebhookDelivery:
    """One event on its way to one endpoint, with the outcome of each try."""

    id: UUID
    organization_id: UUID
    endpoint_id: UUID
    event_id: UUID
    event: WebhookEvent
    payload: Mapping[str, object]
    status: DeliveryStatus
    created_at: datetime
    attempts: int = 0
    next_attempt_at: datetime | None = None
    last_status_code: int | None = None
    last_error: str | None = None
    last_duration_ms: int | None = None
    delivered_at: datetime | None = None

    @property
    def settled(self) -> bool:
        return self.status in (DeliveryStatus.DELIVERED, DeliveryStatus.FAILED)

    def succeeded(self, status_code: int, duration_ms: int, now: datetime) -> None:
        self.attempts += 1
        self.status = DeliveryStatus.DELIVERED
        self.last_status_code, self.last_duration_ms = status_code, duration_ms
        self.last_error, self.next_attempt_at, self.delivered_at = None, None, now

    def failed(
        self,
        status_code: int | None,
        error: str,
        duration_ms: int,
        now: datetime,
        policy: RetryPolicy,
    ) -> datetime | None:
        """Record a failed try; the moment of the next one, or None to give up."""
        self.attempts += 1
        self.last_status_code, self.last_duration_ms = status_code, duration_ms
        self.last_error = error[:500]
        if self.attempts >= policy.max_attempts:
            self.status, self.next_attempt_at = DeliveryStatus.FAILED, None
            return None
        self.status = DeliveryStatus.RETRYING
        self.next_attempt_at = now + policy.delay_after(self.attempts)
        return self.next_attempt_at

    def retry_now(self, now: datetime) -> None:
        """An owner asks to send a settled delivery again."""
        self.status, self.next_attempt_at = DeliveryStatus.PENDING, now
