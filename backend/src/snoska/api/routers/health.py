from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from snoska.api.dependencies import ContainerDep
from snoska.infrastructure.observability.metrics import Metrics

router = APIRouter(tags=["health"])


@router.get("/health/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
async def ready(container: ContainerDep) -> JSONResponse:
    checks = container.health_checks
    results = await asyncio.gather(*(check.check() for check in checks))
    report = {check.name: ok for check, ok in zip(checks, results, strict=True)}
    healthy = all(results)
    return JSONResponse(
        {"status": "ok" if healthy else "degraded", "checks": report},
        status_code=200 if healthy else 503,
    )


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    registry: Metrics = request.app.state.metrics
    return Response(generate_latest(registry.registry), media_type=CONTENT_TYPE_LATEST)
