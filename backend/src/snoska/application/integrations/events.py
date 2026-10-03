from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from snoska.application.documents.parsing import ParsedVersionFollowUp
from snoska.application.shared.jobs import DELIVER_WEBHOOK
from snoska.domain.checks.run import CheckRun, RunStatus
from snoska.domain.documents.version import DocumentVersion
from snoska.domain.integrations.webhooks import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookEvent,
)
from snoska.domain.shared.ids import new_id
from snoska.ports.clock import Clock
from snoska.ports.outbox import OutboxMessage
from snoska.ports.unit_of_work import UnitOfWork

EventData = Mapping[str, object]


class OrganizationEvents:
    """Announces what happened in an organization to its webhook endpoints.

    Called inside the transaction of the change: a delivery and its job are
    committed together with the change, or not at all.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    async def emit(
        self, uow: UnitOfWork, organization_id: UUID, event: WebhookEvent, data: EventData
    ) -> int:
        listed = await uow.webhook_endpoints.list()
        endpoints = [endpoint for endpoint in listed if endpoint.wants(event)]
        event_id = new_id()
        for endpoint in endpoints:
            await self.deliver(uow, organization_id, endpoint, event, event_id, data)
        return len(endpoints)

    async def deliver(
        self,
        uow: UnitOfWork,
        organization_id: UUID,
        endpoint: WebhookEndpoint,
        event: WebhookEvent,
        event_id: UUID,
        data: EventData,
    ) -> WebhookDelivery:
        now = self._clock.now()
        delivery = WebhookDelivery(
            id=new_id(),
            organization_id=organization_id,
            endpoint_id=endpoint.id,
            event_id=event_id,
            event=event,
            payload={
                "id": str(event_id),
                "type": event.value,
                "created_at": now.isoformat(timespec="seconds"),
                "organization_id": str(organization_id),
                "data": dict(data),
            },
            status=DeliveryStatus.PENDING,
            created_at=now,
            next_attempt_at=now,
        )
        await uow.webhook_deliveries.add(delivery)
        await uow.outbox.add(delivery_job(delivery, now))
        return delivery


def delivery_job(delivery: WebhookDelivery, now: datetime) -> OutboxMessage:
    """The job that makes the delivery's next try, not before it is due."""
    return OutboxMessage(
        id=new_id(),
        job_name=DELIVER_WEBHOOK.name,
        payload={
            "organization_id": str(delivery.organization_id),
            "delivery_id": str(delivery.id),
        },
        created_at=now,
        available_at=delivery.next_attempt_at,
    )


class EventFollowUps:
    """Announces parsed versions and settled check runs, from inside the
    transactions that record them (hooks of the parsing and check jobs)."""

    def __init__(self, events: OrganizationEvents) -> None:
        self._events = events

    async def on_parsed(self, uow: UnitOfWork, version: DocumentVersion) -> None:
        document = await uow.documents.get(version.document_id)
        if document is None:
            return
        await self._events.emit(
            uow,
            document.organization_id,
            WebhookEvent.DOCUMENT_PARSED,
            {
                "document_id": str(document.id),
                "title": document.title,
                "version": version.number,
                "pages": version.summary.page_count if version.summary else None,
            },
        )

    async def on_settled(self, uow: UnitOfWork, run: CheckRun) -> None:
        completed = run.status is RunStatus.COMPLETED
        data: dict[str, object] = {
            "run_id": str(run.id),
            "document_id": str(run.document_id),
            "version_id": str(run.version_id),
            "status": run.status.value,
        }
        if completed:
            counts: dict[str, int] = {}
            for finding in await uow.findings.list_for_run(run.id):
                counts[finding.severity.value] = counts.get(finding.severity.value, 0) + 1
            data["findings"] = counts
        else:
            data["failure"] = run.failure_code.value if run.failure_code else None
        event = WebhookEvent.CHECK_COMPLETED if completed else WebhookEvent.CHECK_FAILED
        await self._events.emit(uow, run.organization_id, event, data)


class FollowUps:
    """Several follow-ups of a parsed version, run in order."""

    def __init__(self, *hooks: ParsedVersionFollowUp) -> None:
        self._hooks = hooks

    async def on_parsed(self, uow: UnitOfWork, version: DocumentVersion) -> None:
        for hook in self._hooks:
            await hook.on_parsed(uow, version)
