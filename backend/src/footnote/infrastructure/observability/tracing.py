from __future__ import annotations

from enum import StrEnum

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter


class TracingExporter(StrEnum):
    NONE = "none"
    CONSOLE = "console"
    OTLP = "otlp"


def configure_tracing(
    service_name: str, exporter: TracingExporter, otlp_endpoint: str | None
) -> None:
    """Installs a tracer provider; with ``none`` tracing stays a no-op."""
    if exporter is TracingExporter.NONE:
        return
    span_exporter: SpanExporter = (
        OTLPSpanExporter(endpoint=otlp_endpoint)
        if exporter is TracingExporter.OTLP
        else ConsoleSpanExporter()
    )
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
