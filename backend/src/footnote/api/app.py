from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from footnote.api.errors import install_error_handlers
from footnote.api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from footnote.api.routers import (
    ask,
    autofix,
    billing,
    checks,
    corpus,
    demo,
    documents,
    health,
    me,
    platform,
    workspaces,
)
from footnote.api.routers.admin import audit, integrations, members
from footnote.api.routers.admin import catalog as admin_catalog
from footnote.api.routers.admin import workspaces as workspace_admin
from footnote.bootstrap.container import Container, build_container
from footnote.bootstrap.settings import Settings
from footnote.infrastructure.observability.metrics import Metrics
from footnote.infrastructure.observability.tracing import TracingExporter

API_PREFIX = "/api"
API_VERSION = "1.0.0"
# Multipart framing around the file; the stored file itself is capped exactly.
MULTIPART_OVERHEAD_BYTES = 64 * 1024

ContainerFactory = Callable[[Settings], Awaitable[Container]]


async def _default_container(settings: Settings) -> Container:
    return await build_container(settings)


def create_app(
    settings: Settings | None = None, container_factory: ContainerFactory = _default_container
) -> FastAPI:
    settings = settings or Settings()
    metrics = Metrics()
    tracing = settings.observability.tracing_exporter is not TracingExporter.NONE

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = await container_factory(settings)
        if tracing:
            SQLAlchemyInstrumentor().instrument(engine=container.engine.sync_engine)
        app.state.container = container
        try:
            yield
        finally:
            await container.close()

    app = FastAPI(
        title="Snoska API",
        generate_unique_id_function=lambda route: route.name,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    app.state.metrics = metrics
    install_error_handlers(app)
    for module in (
        health,
        me,
        workspaces,
        workspace_admin,
        members,
        admin_catalog,
        audit,
        integrations,
        billing,
        documents,
        autofix,
        checks,
        corpus,
        ask,
        platform,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
    if settings.integrations.demo_receiver:
        app.include_router(demo.router, prefix=API_PREFIX)
    app.add_middleware(
        BodySizeLimitMiddleware, max_bytes=settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES
    )
    app.add_middleware(RequestContextMiddleware, metrics=metrics)
    if tracing:
        FastAPIInstrumentor.instrument_app(app)
    return app
