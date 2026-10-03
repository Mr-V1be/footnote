from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from snoska.api.schemas.common import ApiModel
from snoska.domain.integrations.api_keys import ApiKey, ApiScope
from snoska.domain.integrations.webhooks import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
)


class ApiKeyOut(ApiModel):
    id: UUID
    name: str
    prefix: str
    scopes: list[ApiScope]
    created_by: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def of(cls, key: ApiKey) -> ApiKeyOut:
        return cls(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            scopes=sorted(key.scopes),
            created_by=key.created_by_label,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            revoked_at=key.revoked_at,
        )


class IssuedKeyOut(ApiModel):
    key: ApiKeyOut
    # Shown once: only a hash is kept.
    token: str


class ApiKeyIn(ApiModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[ApiScope] = Field(min_length=1)


class WebhookOut(ApiModel):
    id: UUID
    url: str
    description: str
    events: list[WebhookEvent]
    active: bool
    created_at: datetime

    @classmethod
    def of(cls, endpoint: WebhookEndpoint) -> WebhookOut:
        return cls(
            id=endpoint.id,
            url=endpoint.url,
            description=endpoint.description,
            events=sorted(endpoint.events),
            active=endpoint.active,
            created_at=endpoint.created_at,
        )


class WebhookWithSecretOut(ApiModel):
    endpoint: WebhookOut
    # Shown on creation and rotation only.
    secret: str


class WebhookIn(ApiModel):
    url: str = Field(min_length=1, max_length=2000)
    description: str = Field(default="", max_length=200)
    events: list[WebhookEvent] = Field(min_length=1)
    active: bool = True


class DeliveryOut(ApiModel):
    id: UUID
    event: WebhookEvent
    status: DeliveryStatus
    attempts: int
    created_at: datetime
    delivered_at: datetime | None
    next_attempt_at: datetime | None
    last_status_code: int | None
    last_error: str | None
    last_duration_ms: int | None
    payload: dict[str, object]

    @classmethod
    def of(cls, delivery: WebhookDelivery) -> DeliveryOut:
        return cls(
            id=delivery.id,
            event=delivery.event,
            status=delivery.status,
            attempts=delivery.attempts,
            created_at=delivery.created_at,
            delivered_at=delivery.delivered_at,
            next_attempt_at=delivery.next_attempt_at,
            last_status_code=delivery.last_status_code,
            last_error=delivery.last_error,
            last_duration_ms=delivery.last_duration_ms,
            payload=dict(delivery.payload),
        )
