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

JOB_SPECS: tuple[JobSpec, ...] = (
    PARSE_DOCUMENT_VERSION,
    INDEX_CORPUS_EDITION,
    RUN_CHECKS,
    DELIVER_WEBHOOK,
)
