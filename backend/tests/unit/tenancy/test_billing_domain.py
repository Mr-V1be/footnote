"""Plans, months and usage as domain rules."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from footnote.domain.billing.plans import Plan, UsageMetric
from footnote.domain.billing.subscription import Subscription, next_month
from footnote.domain.billing.usage import QuotaExceededError, counted_pages, ensure_allowance

LIMITS = dict.fromkeys(UsageMetric, 10)


def test_a_docx_counts_in_printed_pages() -> None:
    assert counted_pages(7, 99_999) == 7
    assert counted_pages(None, 0) == 1
    assert counted_pages(None, 1800) == 1
    assert counted_pages(None, 1801) == 2


def test_a_limit_admits_exactly_its_units() -> None:
    plan = Plan(code="p", rank=0, price_kopecks=0, limits=LIMITS)
    ensure_allowance(plan, UsageMetric.CHECKS, 9, 1)
    with pytest.raises(QuotaExceededError) as raised:
        ensure_allowance(plan, UsageMetric.PAGES, 8, 3)
    assert (raised.value.limit, raised.value.used, raised.value.requested) == (10, 8, 3)


def test_a_month_rolls_over_and_brings_the_scheduled_plan() -> None:
    subscription = Subscription(
        organization_id=uuid4(), plan_code="team", period_start=date(2026, 10, 1)
    )
    subscription.schedule("start")
    assert not subscription.roll(date(2026, 10, 31))
    assert subscription.roll(date(2026, 12, 2))
    assert (subscription.plan_code, subscription.period_start) == ("start", date(2026, 12, 1))
    assert subscription.pending_plan_code is None
    assert next_month(date(2026, 12, 1)) == date(2027, 1, 1)
