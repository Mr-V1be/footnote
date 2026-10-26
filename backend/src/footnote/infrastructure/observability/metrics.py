from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram

LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
JOB_BUCKETS = (0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 900.0)


class Metrics:
    """Process metrics, exposed in the Prometheus text format."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.http_requests = Counter(
            "footnote_http_requests_total",
            "HTTP requests by route and status.",
            ("method", "route", "status"),
            registry=self.registry,
        )
        self.http_latency = Histogram(
            "footnote_http_request_duration_seconds",
            "HTTP request latency by route.",
            ("method", "route"),
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.jobs = Counter(
            "footnote_jobs_total",
            "Background jobs by name and outcome.",
            ("job", "outcome"),
            registry=self.registry,
        )
        self.job_duration = Histogram(
            "footnote_job_duration_seconds",
            "Background job duration.",
            ("job",),
            buckets=JOB_BUCKETS,
            registry=self.registry,
        )
