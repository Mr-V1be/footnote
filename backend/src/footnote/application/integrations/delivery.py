from __future__ import annotations

import json
from uuid import UUID

import structlog

from footnote.application.integrations.events import delivery_job
from footnote.domain.integrations.webhooks import RetryPolicy, signature_header
from footnote.ports.clock import Clock
from footnote.ports.integrations.transport import WebhookTransport
from footnote.ports.jobs import JobPayload
from footnote.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)

USER_AGENT = "Snoska-Webhooks/1.0"


class DeliverWebhook:
    """Background job: one try of one delivery.

    The body is signed with the endpoint's secret (header ``Snoska-Signature:
    t=<unix time>,v1=<HMAC-SHA256 of "t.body">``). On failure the next try is
    scheduled by the delivery's retry policy; after the last one it is
    marked failed. A delivery already settled is left alone (at-least-once
    queues may bring a job twice).
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        transport: WebhookTransport,
        clock: Clock,
        policy: RetryPolicy | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._transport = transport
        self._clock = clock
        self._policy = policy or RetryPolicy()

    async def __call__(self, payload: JobPayload) -> None:
        organization_id = UUID(payload["organization_id"])
        delivery_id = UUID(payload["delivery_id"])
        async with self._uow_factory.for_tenant(organization_id) as uow:
            delivery = await uow.webhook_deliveries.get(delivery_id)
            endpoint = await uow.webhook_endpoints.get(delivery.endpoint_id) if delivery else None
        if delivery is None or endpoint is None or delivery.settled:
            return
        body = json.dumps(delivery.payload, ensure_ascii=False, separators=(",", ":")).encode()
        timestamp = int(self._clock.now().timestamp())
        result = await self._transport.post(
            endpoint.url,
            body,
            {
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "Snoska-Event": delivery.event.value,
                "Snoska-Delivery": str(delivery.id),
                "Snoska-Signature": signature_header(endpoint.secret, timestamp, body),
            },
        )
        async with self._uow_factory.for_tenant(organization_id) as uow:
            current = await uow.webhook_deliveries.lock(delivery_id)
            if current is None or current.settled:
                return
            now = self._clock.now()
            if result.ok and result.status_code is not None:
                current.succeeded(result.status_code, result.duration_ms, now)
            else:
                error = result.error or f"HTTP {result.status_code}"
                next_try = current.failed(
                    result.status_code, error, result.duration_ms, now, self._policy
                )
                if next_try is not None:
                    await uow.outbox.add(delivery_job(current, now))
            await uow.webhook_deliveries.save(current)
            await uow.commit()
        log.info(
            "webhooks.delivery_tried",
            delivery_id=str(delivery_id),
            status=current.status,
            code=result.status_code,
        )
