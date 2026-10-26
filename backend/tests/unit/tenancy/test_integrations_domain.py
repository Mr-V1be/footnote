"""API keys and webhook deliveries as domain objects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from footnote.domain.integrations.api_keys import ApiScope, issue_key, prefix_of
from footnote.domain.integrations.webhooks import (
    DeliveryStatus,
    InvalidWebhookUrlError,
    RetryPolicy,
    WebhookDelivery,
    WebhookEvent,
    signature_header,
    validate_url,
    verify_signature,
)
from footnote.domain.tenancy.permissions import Permission

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def test_a_key_is_found_by_its_prefix_and_proven_by_its_secret() -> None:
    issued = issue_key(
        id=uuid4(),
        organization_id=uuid4(),
        name="CRM",
        scopes=frozenset({ApiScope.CHECKS_RUN}),
        created_by=uuid4(),
        created_by_label="Анна",
        now=NOW,
    )
    key, token = issued.key, issued.token
    assert prefix_of(token) == key.prefix
    assert key.matches(token)
    assert not key.matches(token + "x")
    assert issued.token not in key.token_hash
    assert key.permissions == {Permission.DOCUMENTS_READ, Permission.CHECKS_RUN}
    assert prefix_of("eyJhbGciOi.jwt") is None
    assert key.note_use(NOW)
    assert not key.note_use(NOW + timedelta(seconds=20)), "uses are recorded once a minute"


def test_signatures_cover_the_time_and_the_body() -> None:
    header = signature_header("whsec_a", 1_790_000_000, b'{"x":1}')
    assert verify_signature("whsec_a", header, b'{"x":1}')
    assert not verify_signature("whsec_a", header, b'{"x":2}')
    assert not verify_signature("whsec_a", header.replace("1790000000", "1790000001"), b'{"x":1}')
    assert not verify_signature("whsec_a", "garbage", b"")


def test_a_failing_delivery_backs_off_then_gives_up() -> None:
    delivery = WebhookDelivery(
        id=uuid4(),
        organization_id=uuid4(),
        endpoint_id=uuid4(),
        event_id=uuid4(),
        event=WebhookEvent.CHECK_COMPLETED,
        payload={},
        status=DeliveryStatus.PENDING,
        created_at=NOW,
    )
    policy = RetryPolicy(max_attempts=3)
    first = delivery.failed(500, "HTTP 500", 10, NOW, policy)
    second = delivery.failed(None, "ConnectTimeout", 10, NOW, policy)
    assert first == NOW + timedelta(seconds=30)
    assert second == NOW + timedelta(minutes=2)
    assert delivery.status is DeliveryStatus.RETRYING
    assert delivery.failed(502, "HTTP 502", 10, NOW, policy) is None
    assert delivery.status is DeliveryStatus.FAILED


@pytest.mark.parametrize(
    "url", ["http://hooks.example", "ftp://hooks.example", "https://user:pw@hooks.example", "/x"]
)
def test_endpoints_are_public_https_addresses(url: str) -> None:
    with pytest.raises(InvalidWebhookUrlError):
        validate_url(url, allow_http=False)


def test_the_demo_stand_may_use_plain_http() -> None:
    assert validate_url(" http://127.0.0.1:46301/x ", allow_http=True) == "http://127.0.0.1:46301/x"
