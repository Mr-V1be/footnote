from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from footnote.application.audit.trail import AuditTrail
from footnote.application.integrations.events import OrganizationEvents, delivery_job
from footnote.application.shared.pagination import Page, clamp_page_size, next_page
from footnote.domain.audit.event import AuditAction, AuditTarget
from footnote.domain.integrations.webhooks import (
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
    new_secret,
    validate_url,
    verify_signature,
)
from footnote.domain.shared.errors import InvalidStateError, NotFoundError
from footnote.domain.shared.ids import new_id
from footnote.domain.tenancy.access import OrganizationAccess
from footnote.domain.tenancy.permissions import Permission
from footnote.ports.clock import Clock
from footnote.ports.pagination import TimeCursor
from footnote.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


class WebhookNotFoundError(NotFoundError):
    code = "webhook_not_found"


class DeliveryInFlightError(InvalidStateError):
    code = "delivery_in_flight"


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    url: str
    description: str
    events: frozenset[WebhookEvent]
    active: bool = True


def _target(endpoint: WebhookEndpoint) -> AuditTarget:
    return AuditTarget(type="webhook", id=str(endpoint.id), label=endpoint.url)


class WebhookEndpoints:
    """An organization's webhook endpoints, their secrets and delivery log."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        events: OrganizationEvents,
        audit: AuditTrail,
        clock: Clock,
        *,
        allow_http: bool,
    ) -> None:
        self._uow_factory = uow_factory
        self._events = events
        self._audit = audit
        self._clock = clock
        self._allow_http = allow_http

    async def list(self, access: OrganizationAccess) -> Sequence[WebhookEndpoint]:
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            return await uow.webhook_endpoints.list()

    async def create(self, access: OrganizationAccess, spec: EndpointSpec) -> WebhookEndpoint:
        """The returned endpoint carries its secret: the only time it is shown."""
        access.require(Permission.INTEGRATIONS_MANAGE)
        endpoint = WebhookEndpoint(
            id=new_id(),
            organization_id=access.organization_id,
            url=validate_url(spec.url, allow_http=self._allow_http),
            description=spec.description,
            events=spec.events,
            secret=new_secret(),
            active=spec.active,
            created_at=self._clock.now(),
        )
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await uow.webhook_endpoints.add(endpoint)
            await self._audit.record(
                uow,
                access,
                AuditAction.WEBHOOK_CREATED,
                _target(endpoint),
                {"events": ",".join(sorted(event.value for event in spec.events))},
            )
            await uow.commit()
        return endpoint

    async def update(
        self, access: OrganizationAccess, endpoint_id: UUID, spec: EndpointSpec
    ) -> WebhookEndpoint:
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            endpoint = await self._existing(uow, endpoint_id)
            # replace() validates the new state like a new endpoint.
            updated = replace(
                endpoint,
                url=validate_url(spec.url, allow_http=self._allow_http),
                description=spec.description,
                events=spec.events,
                active=spec.active,
            )
            await uow.webhook_endpoints.save(updated)
            await self._audit.record(
                uow, access, AuditAction.WEBHOOK_UPDATED, _target(updated), {"active": spec.active}
            )
            await uow.commit()
        return updated

    async def rotate_secret(self, access: OrganizationAccess, endpoint_id: UUID) -> WebhookEndpoint:
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            endpoint = await self._existing(uow, endpoint_id)
            endpoint.secret = new_secret()
            await uow.webhook_endpoints.save(endpoint)
            await self._audit.record(
                uow, access, AuditAction.WEBHOOK_UPDATED, _target(endpoint), {"secret": "rotated"}
            )
            await uow.commit()
        return endpoint

    async def delete(self, access: OrganizationAccess, endpoint_id: UUID) -> None:
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            endpoint = await self._existing(uow, endpoint_id)
            await uow.webhook_endpoints.delete(endpoint_id)
            await self._audit.record(uow, access, AuditAction.WEBHOOK_DELETED, _target(endpoint))
            await uow.commit()

    async def deliveries(
        self,
        access: OrganizationAccess,
        endpoint_id: UUID,
        after: TimeCursor | None = None,
        limit: int | None = None,
    ) -> Page[WebhookDelivery, TimeCursor]:
        """The delivery log of an endpoint, newest first, a page at a time."""
        access.require(Permission.INTEGRATIONS_MANAGE)
        size = clamp_page_size(limit)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._existing(uow, endpoint_id)
            rows = await uow.webhook_deliveries.list_for_endpoint(
                endpoint_id, after=after, limit=size + 1
            )
        return next_page(rows, size, lambda delivery: TimeCursor(delivery.created_at, delivery.id))

    async def ping(self, access: OrganizationAccess, endpoint_id: UUID) -> WebhookDelivery:
        """Send a test event to one endpoint."""
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            endpoint = await self._existing(uow, endpoint_id)
            delivery = await self._events.deliver(
                uow,
                access.organization_id,
                endpoint,
                WebhookEvent.PING,
                new_id(),
                {"message": "Тестовое событие", "requested_by": access.actor.label},
            )
            await uow.commit()
        return delivery

    async def redeliver(
        self, access: OrganizationAccess, endpoint_id: UUID, delivery_id: UUID
    ) -> WebhookDelivery:
        access.require(Permission.INTEGRATIONS_MANAGE)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._existing(uow, endpoint_id)
            delivery = await uow.webhook_deliveries.lock(delivery_id)
            if delivery is None or delivery.endpoint_id != endpoint_id:
                raise WebhookNotFoundError("delivery not found")
            if not delivery.settled:
                raise DeliveryInFlightError("the delivery is still being tried")
            now = self._clock.now()
            delivery.retry_now(now)
            await uow.webhook_deliveries.save(delivery)
            await uow.outbox.add(delivery_job(delivery, now))
            await uow.commit()
        return delivery

    async def accept_demo_delivery(
        self, organization_id: UUID, endpoint_id: UUID, header: str, body: bytes
    ) -> bool:
        """The demo stand's own receiver: is the delivery signed by the endpoint?"""
        async with self._uow_factory.for_tenant(organization_id) as uow:
            endpoint = await uow.webhook_endpoints.get(endpoint_id)
        return endpoint is not None and verify_signature(endpoint.secret, header, body)

    @staticmethod
    async def _existing(uow: UnitOfWork, endpoint_id: UUID) -> WebhookEndpoint:
        endpoint = await uow.webhook_endpoints.get(endpoint_id)
        if endpoint is None:
            raise WebhookNotFoundError("webhook endpoint not found")
        return endpoint
