"""ASGI entry point: ``uvicorn footnote.api.asgi:app``."""

from __future__ import annotations

from footnote.api.app import create_app
from footnote.bootstrap.settings import Settings
from footnote.infrastructure.observability.logging import configure_logging
from footnote.infrastructure.observability.tracing import configure_tracing

_settings = Settings()
configure_logging(_settings.observability.log_level, json=_settings.observability.log_json)
configure_tracing(
    "footnote-api", _settings.observability.tracing_exporter, _settings.observability.otlp_endpoint
)
app = create_app(_settings)
