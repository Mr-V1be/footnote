from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.integrations.api_keys import ApiKey, ApiScope
from snoska.domain.integrations.webhooks import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
)
from snoska.infrastructure.persistence.tables.integrations import (
    api_keys,
    webhook_deliveries,
    webhook_endpoints,
)
from snoska.ports.integrations.transport import SecretBox


def _key(row: RowMapping) -> ApiKey:
    return ApiKey(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        prefix=row["prefix"],
        token_hash=row["token_hash"],
        scopes=frozenset(ApiScope(scope) for scope in row["scopes"]),
        created_by=row["created_by"],
        created_by_label=row["created_by_label"],
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        revoked_at=row["revoked_at"],
    )


class SqlApiKeyRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def list(self) -> Sequence[ApiKey]:
        result = await self._connection.execute(
            select(api_keys).order_by(
                api_keys.c.revoked_at.nulls_first(), api_keys.c.created_at.desc()
            )
        )
        return [_key(row) for row in result.mappings()]

    async def get(self, key_id: UUID) -> ApiKey | None:
        row = (
            (await self._connection.execute(select(api_keys).where(api_keys.c.id == key_id)))
            .mappings()
            .first()
        )
        return _key(row) if row else None

    async def find_by_prefix(self, prefix: str) -> ApiKey | None:
        row = (
            (await self._connection.execute(select(api_keys).where(api_keys.c.prefix == prefix)))
            .mappings()
            .first()
        )
        return _key(row) if row else None

    async def add(self, key: ApiKey) -> None:
        await self._connection.execute(insert(api_keys).values(**self._values(key)))

    async def save(self, key: ApiKey) -> None:
        await self._connection.execute(
            update(api_keys)
            .where(api_keys.c.id == key.id)
            .values(name=key.name, last_used_at=key.last_used_at, revoked_at=key.revoked_at)
        )

    @staticmethod
    def _values(key: ApiKey) -> dict[str, Any]:
        return {
            "id": key.id,
            "organization_id": key.organization_id,
            "name": key.name,
            "prefix": key.prefix,
            "token_hash": key.token_hash,
            "scopes": sorted(scope.value for scope in key.scopes),
            "created_by": key.created_by,
            "created_by_label": key.created_by_label,
            "created_at": key.created_at,
            "last_used_at": key.last_used_at,
            "revoked_at": key.revoked_at,
        }


class SqlWebhookEndpointRepository:
    def __init__(self, connection: AsyncConnection, box: SecretBox) -> None:
        self._connection = connection
        self._box = box

    def _endpoint(self, row: RowMapping) -> WebhookEndpoint:
        return WebhookEndpoint(
            id=row["id"],
            organization_id=row["organization_id"],
            url=row["url"],
            description=row["description"],
            events=frozenset(WebhookEvent(event) for event in row["events"]),
            secret=self._box.open(row["secret_sealed"]),
            active=row["active"],
            created_at=row["created_at"],
        )

    def _values(self, endpoint: WebhookEndpoint) -> dict[str, Any]:
        return {
            "url": endpoint.url,
            "description": endpoint.description,
            "events": sorted(event.value for event in endpoint.events),
            "secret_sealed": self._box.seal(endpoint.secret),
            "active": endpoint.active,
        }

    async def list(self) -> Sequence[WebhookEndpoint]:
        result = await self._connection.execute(
            select(webhook_endpoints).order_by(webhook_endpoints.c.created_at)
        )
        return [self._endpoint(row) for row in result.mappings()]

    async def get(self, endpoint_id: UUID) -> WebhookEndpoint | None:
        row = (
            (
                await self._connection.execute(
                    select(webhook_endpoints).where(webhook_endpoints.c.id == endpoint_id)
                )
            )
            .mappings()
            .first()
        )
        return self._endpoint(row) if row else None

    async def add(self, endpoint: WebhookEndpoint) -> None:
        await self._connection.execute(
            insert(webhook_endpoints).values(
                id=endpoint.id,
                organization_id=endpoint.organization_id,
                created_at=endpoint.created_at,
                **self._values(endpoint),
            )
        )

    async def save(self, endpoint: WebhookEndpoint) -> None:
        await self._connection.execute(
            update(webhook_endpoints)
            .where(webhook_endpoints.c.id == endpoint.id)
            .values(**self._values(endpoint))
        )

    async def delete(self, endpoint_id: UUID) -> None:
        await self._connection.execute(
            delete(webhook_endpoints).where(webhook_endpoints.c.id == endpoint_id)
        )


def _delivery(row: RowMapping) -> WebhookDelivery:
    return WebhookDelivery(
        id=row["id"],
        organization_id=row["organization_id"],
        endpoint_id=row["endpoint_id"],
        event_id=row["event_id"],
        event=WebhookEvent(row["event"]),
        payload=dict(row["payload"]),
        status=DeliveryStatus(row["status"]),
        created_at=row["created_at"],
        attempts=row["attempts"],
        next_attempt_at=row["next_attempt_at"],
        last_status_code=row["last_status_code"],
        last_error=row["last_error"],
        last_duration_ms=row["last_duration_ms"],
        delivered_at=row["delivered_at"],
    )


class SqlWebhookDeliveryRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, delivery: WebhookDelivery) -> None:
        await self._connection.execute(
            insert(webhook_deliveries).values(
                id=delivery.id,
                organization_id=delivery.organization_id,
                endpoint_id=delivery.endpoint_id,
                event_id=delivery.event_id,
                event=delivery.event.value,
                payload=dict(delivery.payload),
                created_at=delivery.created_at,
                **self._state(delivery),
            )
        )

    @staticmethod
    def _state(delivery: WebhookDelivery) -> dict[str, Any]:
        return {
            "status": delivery.status.value,
            "attempts": delivery.attempts,
            "next_attempt_at": delivery.next_attempt_at,
            "last_status_code": delivery.last_status_code,
            "last_error": delivery.last_error,
            "last_duration_ms": delivery.last_duration_ms,
            "delivered_at": delivery.delivered_at,
        }

    async def get(self, delivery_id: UUID) -> WebhookDelivery | None:
        row = (
            (
                await self._connection.execute(
                    select(webhook_deliveries).where(webhook_deliveries.c.id == delivery_id)
                )
            )
            .mappings()
            .first()
        )
        return _delivery(row) if row else None

    async def lock(self, delivery_id: UUID) -> WebhookDelivery | None:
        row = (
            (
                await self._connection.execute(
                    select(webhook_deliveries)
                    .where(webhook_deliveries.c.id == delivery_id)
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        return _delivery(row) if row else None

    async def save(self, delivery: WebhookDelivery) -> None:
        await self._connection.execute(
            update(webhook_deliveries)
            .where(webhook_deliveries.c.id == delivery.id)
            .values(**self._state(delivery))
        )

    async def list_for_endpoint(
        self, endpoint_id: UUID, *, limit: int
    ) -> Sequence[WebhookDelivery]:
        result = await self._connection.execute(
            select(webhook_deliveries)
            .where(webhook_deliveries.c.endpoint_id == endpoint_id)
            .order_by(webhook_deliveries.c.created_at.desc())
            .limit(limit)
        )
        return [_delivery(row) for row in result.mappings()]
