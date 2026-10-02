"""ASGI entry point: ``uvicorn snoska.api.asgi:app``."""

from __future__ import annotations

from snoska.api.app import create_app
from snoska.bootstrap.settings import Settings
from snoska.infrastructure.observability.logging import configure_logging
from snoska.infrastructure.observability.tracing import configure_tracing

_settings = Settings()
configure_logging(_settings.observability.log_level, json=_settings.observability.log_json)
configure_tracing(
    "snoska-api", _settings.observability.tracing_exporter, _settings.observability.otlp_endpoint
)
app = create_app(_settings)
