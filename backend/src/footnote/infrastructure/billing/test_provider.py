from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx

from footnote.ports.billing.payments import (
    InvalidNotificationError,
    PaymentNotification,
    PaymentRequest,
    PaymentSession,
    PaymentStatus,
)

SIGNATURE_HEADER = "Test-Payments-Signature"


@dataclass(frozen=True, slots=True)
class TestPayment:
    """A payment of the test provider, carried in its signed token."""

    payment_id: str
    invoice_id: UUID
    organization_id: UUID
    amount_kopecks: int
    currency: str
    description: str
    return_url: str


class TestPaymentProvider:
    """A payment provider in test mode that runs inside the stand.

    It opens payments without any account: the checkout page lets a person
    confirm or decline, and the provider then notifies the platform with a
    webhook signed by its secret, exactly like a live provider would. No
    money moves and no card data is ever asked for.
    """

    name = "test"
    __test__ = False  # not a pytest test class

    def __init__(self, secret: str, web_url: str) -> None:
        if not secret:
            raise ValueError("SNOSKA_PAYMENTS_TEST_SECRET is not set")
        self._secret = secret.encode()
        self._web_url = web_url.rstrip("/")

    def _sign(self, data: bytes) -> str:
        return hmac.new(self._secret, data, hashlib.sha256).hexdigest()

    async def open_payment(self, request: PaymentRequest) -> PaymentSession:
        payment = TestPayment(
            payment_id=f"tp_{uuid4().hex}",
            invoice_id=request.invoice_id,
            organization_id=request.organization_id,
            amount_kopecks=request.amount_kopecks,
            currency=request.currency,
            description=request.description,
            return_url=request.return_url,
        )
        token = self.token(payment)
        url = f"{self._web_url}/pay/test/{payment.payment_id}?token={quote(token)}"
        return PaymentSession(payment_id=payment.payment_id, confirmation_url=url)

    def token(self, payment: TestPayment) -> str:
        raw = json.dumps(
            {
                "p": payment.payment_id,
                "i": str(payment.invoice_id),
                "o": str(payment.organization_id),
                "a": payment.amount_kopecks,
                "c": payment.currency,
                "d": payment.description,
                "r": payment.return_url,
            },
            separators=(",", ":"),
        ).encode()
        body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        return f"{body}.{self._sign(raw)}"

    def payment(self, payment_id: str, token: str) -> TestPayment:
        """Read a checkout token; raise InvalidNotificationError if forged."""
        try:
            body, signature = token.rsplit(".", 1)
            raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            raise InvalidNotificationError("malformed payment token") from exc
        if not hmac.compare_digest(signature, self._sign(raw)) or data["p"] != payment_id:
            raise InvalidNotificationError("the payment token is not ours")
        return TestPayment(
            payment_id=data["p"],
            invoice_id=UUID(data["i"]),
            organization_id=UUID(data["o"]),
            amount_kopecks=int(data["a"]),
            currency=data["c"],
            description=data["d"],
            return_url=data["r"],
        )

    def notification(
        self, payment: TestPayment, status: PaymentStatus
    ) -> tuple[bytes, dict[str, str]]:
        """The webhook the provider sends once a person decided."""
        body = json.dumps(
            {
                "event": f"evt_{uuid4().hex}",
                "payment": payment.payment_id,
                "invoice": str(payment.invoice_id),
                "organization": str(payment.organization_id),
                "status": status.value,
                "amount": payment.amount_kopecks,
            },
            separators=(",", ":"),
        ).encode()
        return body, {"Content-Type": "application/json", SIGNATURE_HEADER: self._sign(body)}

    def parse_notification(self, body: bytes, headers: dict[str, str]) -> PaymentNotification:
        given = next(
            (value for key, value in headers.items() if key.lower() == SIGNATURE_HEADER.lower()),
            "",
        )
        if not hmac.compare_digest(given, self._sign(body)):
            raise InvalidNotificationError("the notification is not signed by the provider")
        try:
            data = json.loads(body)
            return PaymentNotification(
                event_id=str(data["event"]),
                payment_id=str(data["payment"]),
                invoice_id=UUID(data["invoice"]),
                organization_id=UUID(data["organization"]),
                status=PaymentStatus(data["status"]),
                amount_kopecks=int(data["amount"]),
            )
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise InvalidNotificationError("malformed notification") from exc


class TestPaymentNotifier:
    """Background job of the test provider: sends its webhook to the platform."""

    __test__ = False

    def __init__(self, http: httpx.AsyncClient, webhook_url: str) -> None:
        self._http = http
        self._webhook_url = webhook_url

    async def __call__(self, payload: Mapping[str, str]) -> None:
        body = payload["body"].encode()
        headers = json.loads(payload["headers"])
        response = await self._http.post(self._webhook_url, content=body, headers=headers)
        response.raise_for_status()
