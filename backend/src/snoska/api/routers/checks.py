from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from snoska.api.dependencies import ContainerDep, CorpusReaderDep, OrganizationAccessDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.schemas.checks import (
    CheckCatalogOut,
    CheckReportOut,
    FindingOut,
    ModelsOut,
    ReviewIn,
    RunOut,
)
from snoska.domain.checks.run import CheckRun

router = APIRouter(prefix="/v1", tags=["checks"], responses=PROBLEM_RESPONSES)

# A comment line keeps idle connections open through proxies.
KEEP_ALIVE_SECONDS = 15.0
EVENT_STREAM = "text/event-stream"


@router.post(
    "/organizations/{organization}/documents/{document_id}/versions/{number}/checks",
    response_model=RunOut,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_check(
    container: ContainerDep, access: OrganizationAccessDep, document_id: UUID, number: int
) -> RunOut:
    """Check the version again with the current catalogue (or join a pending run)."""
    return RunOut.of(await container.checks.request(access, document_id, number))


@router.get(
    "/organizations/{organization}/documents/{document_id}/versions/{number}/checks/latest",
    response_model=CheckReportOut | None,
    response_model_by_alias=True,
)
async def latest_check(
    container: ContainerDep, access: OrganizationAccessDep, document_id: UUID, number: int
) -> CheckReportOut | None:
    """The latest run of the version with its results and findings; null if never checked."""
    report = await container.checks.latest(access, document_id, number)
    if report is None:
        return None
    citations = await container.checks.citations()
    return CheckReportOut.of(report, container.checks.catalog, citations)


@router.get(
    "/organizations/{organization}/check-runs/{run_id}",
    response_model=RunOut,
    response_model_by_alias=True,
)
async def get_run(container: ContainerDep, access: OrganizationAccessDep, run_id: UUID) -> RunOut:
    return RunOut.of(await container.checks.run(access, run_id))


def _event(run: CheckRun) -> str:
    return f"event: run\ndata: {RunOut.of(run).model_dump_json(by_alias=True)}\n\n"


async def _with_keep_alive(runs: AsyncIterator[CheckRun]) -> AsyncIterator[str]:
    pending: asyncio.Task[CheckRun] | None = None
    try:
        while True:
            pending = pending or asyncio.ensure_future(anext(runs))
            done, _ = await asyncio.wait({pending}, timeout=KEEP_ALIVE_SECONDS)
            if not done:
                yield ": keep-alive\n\n"
                continue
            try:
                run = pending.result()
            except StopAsyncIteration:
                break
            pending = None
            yield _event(run)
        yield "event: end\ndata: {}\n\n"
    finally:
        if pending is not None and not pending.done():
            pending.cancel()


@router.get(
    "/organizations/{organization}/check-runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {EVENT_STREAM: {}}, "description": "Server-sent run events"}},
)
async def run_events(
    container: ContainerDep, access: OrganizationAccessDep, run_id: UUID
) -> StreamingResponse:
    """Progress of a run as server-sent events: `run` on every change, `end` when settled."""
    await container.checks.run(access, run_id)
    stream = _with_keep_alive(container.check_progress.stream(access, run_id))
    return StreamingResponse(
        stream,
        media_type=EVENT_STREAM,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.patch(
    "/organizations/{organization}/findings/{finding_id}",
    response_model=FindingOut,
    response_model_by_alias=True,
)
async def review_finding(
    container: ContainerDep, access: OrganizationAccessDep, finding_id: UUID, body: ReviewIn
) -> FindingOut:
    """Accept, reject, mark fixed or reopen a finding (optimistic concurrency by revision)."""
    finding = await container.checks.review(access, finding_id, body.review, body.revision)
    return FindingOut.of(finding)


@router.get("/checks/catalog", response_model=CheckCatalogOut, response_model_by_alias=True)
async def check_catalog(container: ContainerDep, _: CorpusReaderDep) -> CheckCatalogOut:
    """Every check the product runs, what it requires and what it cites."""
    ai = container.ai
    models = ModelsOut(
        configured=ai.configured,
        language_model=ai.language_model.model or None,
        embedding_model=ai.embedder.model or None,
    )
    return CheckCatalogOut.of(container.checks.catalog, await container.checks.citations(), models)
