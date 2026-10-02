from __future__ import annotations

from snoska.ports.jobs import JobSpec

PARSE_DOCUMENT_VERSION = JobSpec(
    name="documents.parse_version",
    queue="documents",
    max_retries=4,
    time_limit_seconds=15 * 60,
)

EMBED_CORPUS_EDITION = JobSpec(
    name="corpus.embed_edition",
    queue="corpus",
    max_retries=10,
    time_limit_seconds=60 * 60,
    min_backoff_ms=10_000,
)

JOB_SPECS: tuple[JobSpec, ...] = (PARSE_DOCUMENT_VERSION, EMBED_CORPUS_EDITION)
