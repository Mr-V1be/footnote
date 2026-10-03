from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from snoska.domain.integrations.api_keys import ApiKey
from snoska.domain.integrations.webhooks import WebhookDelivery, WebhookEndpoint
from snoska.ports.pagination import TimeCursor


class ApiKeyRepository(Protocol):
    """Tenant-scoped."""

    async def list(self) -> Sequence[ApiKey]: ...

    async def get(self, key_id: UUID) -> ApiKey | None: ...

    async def find_by_prefix(self, prefix: str) -> ApiKey | None: ...

    async def add(self, key: ApiKey) -> None: ...

    async def save(self, key: ApiKey) -> None: ...


class WebhookEndpointRepository(Protocol):
    """Tenant-scoped. Secrets are sealed at rest by the adapter."""

    async def list(self) -> Sequence[WebhookEndpoint]: ...

    async def get(self, endpoint_id: UUID) -> WebhookEndpoint | None: ...

    async def add(self, endpoint: WebhookEndpoint) -> None: ...

    async def save(self, endpoint: WebhookEndpoint) -> None: ...

    async def delete(self, endpoint_id: UUID) -> None: ...


class WebhookDeliveryRepository(Protocol):
    """Tenant-scoped."""

    async def add(self, delivery: WebhookDelivery) -> None: ...

    async def get(self, delivery_id: UUID) -> WebhookDelivery | None: ...

    async def lock(self, delivery_id: UUID) -> WebhookDelivery | None: ...

    async def save(self, delivery: WebhookDelivery) -> None: ...

    async def list_for_endpoint(
        self, endpoint_id: UUID, *, after: TimeCursor | None, limit: int
    ) -> Sequence[WebhookDelivery]:
        """Newest first, strictly after the cursor."""
        ...
