from __future__ import annotations

import json
from dataclasses import dataclass

from footnote.domain.shared.ids import new_id
from footnote.infrastructure.billing.test_provider import TestPayment, TestPaymentProvider
from footnote.ports.billing.payments import PaymentStatus
from footnote.ports.clock import Clock
from footnote.ports.outbox import OutboxMessage
from footnote.ports.unit_of_work import UnitOfWorkFactory

NOTIFY_JOB = "payments.test_notify"


@dataclass(frozen=True, slots=True)
class Decision:
    status: PaymentStatus
    return_url: str


class TestGateway:
    """The provider's side of the test payments: its checkout and its
    notification, queued like a provider's delayed webhook."""

    __test__ = False

    def __init__(
        self, provider: TestPaymentProvider, uow_factory: UnitOfWorkFactory, clock: Clock
    ) -> None:
        self._provider = provider
        self._uow_factory = uow_factory
        self._clock = clock

    def checkout(self, payment_id: str, token: str) -> TestPayment:
        return self._provider.payment(payment_id, token)

    async def decide(self, payment_id: str, token: str, status: PaymentStatus) -> Decision:
        payment = self._provider.payment(payment_id, token)
        body, headers = self._provider.notification(payment, status)
        async with self._uow_factory.for_platform() as uow:
            await uow.outbox.add(
                OutboxMessage(
                    id=new_id(),
                    job_name=NOTIFY_JOB,
                    payload={"body": body.decode(), "headers": json.dumps(headers)},
                    created_at=self._clock.now(),
                )
            )
            await uow.commit()
        return Decision(status=status, return_url=payment.return_url)
