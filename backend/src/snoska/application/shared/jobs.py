from __future__ import annotations

from snoska.ports.jobs import JobSpec

PARSE_DOCUMENT_VERSION = JobSpec(
    name="documents.parse_version",
    queue="documents",
    max_retries=4,
    time_limit_seconds=15 * 60,
)

INDEX_CORPUS_EDITION = JobSpec(
    name="corpus.index_edition",
    queue="corpus",
    max_retries=10,
    time_limit_seconds=60 * 60,
    min_backoff_ms=10_000,
)

RUN_CHECKS = JobSpec(
    name="checks.run",
    queue="checks",
    max_retries=3,
    time_limit_seconds=30 * 60,
    min_backoff_ms=5_000,
)

# One try of one webhook delivery; retries are scheduled by the delivery
# itself (its backoff is visible to the owner), not by the queue.
DELIVER_WEBHOOK = JobSpec(
    name="webhooks.deliver",
    queue="webhooks",
    max_retries=2,
    time_limit_seconds=60,
)

# The test payment provider's webhook to the platform.
NOTIFY_TEST_PAYMENT = JobSpec(
    name="payments.test_notify",
    queue="payments",
    max_retries=5,
    time_limit_seconds=60,
)

# The weekly look at the official portal for new redactions of the acts.
WATCH_CORPUS = JobSpec(
    name="corpus.watch",
    queue="corpus",
    max_retries=3,
    time_limit_seconds=10 * 60,
    min_backoff_ms=60_000,
)

# Hourly: checks that waited for the model's daily allowance run again once
# the allowance renews.
RESUME_CHECKS = JobSpec(
    name="checks.resume",
    queue="checks",
    max_retries=1,
    time_limit_seconds=5 * 60,
)

JOB_SPECS: tuple[JobSpec, ...] = (
    PARSE_DOCUMENT_VERSION,
    INDEX_CORPUS_EDITION,
    RUN_CHECKS,
    DELIVER_WEBHOOK,
    NOTIFY_TEST_PAYMENT,
    WATCH_CORPUS,
    RESUME_CHECKS,
)
