from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from snoska.api.cursors import decode_audit_cursor, encode_audit_cursor
from snoska.api.dependencies import ContainerDep, OrganizationAccessDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.schemas.admin.audit import AuditEventOut, AuditPageOut
from snoska.domain.audit.event import AuditAction, AuditEvent
from snoska.domain.tenancy.access import ActorKind
from snoska.ports.audit.log import AuditFilter

router = APIRouter(
    prefix="/v1/organizations/{organization}/audit", tags=["admin"], responses=PROBLEM_RESPONSES
)

CSV_HEADER = ("occurred_at", "actor_kind", "actor", "action", "target_type", "target", "details")


def _filter(
    category: list[str] | None,
    action: list[AuditAction] | None,
    actor_kind: ActorKind | None,
    since: datetime | None,
    until: datetime | None,
) -> AuditFilter:
    actions = set(action or [])
    if category:
        actions |= {item for item in AuditAction if item.category in category}
    return AuditFilter(actions=frozenset(actions), actor_kind=actor_kind, since=since, until=until)


@router.get("", response_model=AuditPageOut, response_model_by_alias=True)
async def audit_log(
    container: ContainerDep,
    access: OrganizationAccessDep,
    category: Annotated[list[str] | None, Query()] = None,
    action: Annotated[list[AuditAction] | None, Query()] = None,
    actor_kind: Annotated[ActorKind | None, Query(alias="actorKind")] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> AuditPageOut:
    """Who did what, newest first (owners and lawyers)."""
    page = await container.audit.page(
        access,
        _filter(category, action, actor_kind, since, until),
        decode_audit_cursor(cursor) if cursor else None,
        limit,
    )
    return AuditPageOut(
        items=[AuditEventOut.of(event) for event in page.items],
        next_cursor=encode_audit_cursor(page.next_cursor) if page.next_cursor else None,
    )


# A spreadsheet runs a cell starting with these as a formula; names and
# titles come from users, so such a cell is written as text.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: str) -> str:
    return f"'{value}" if value.startswith(FORMULA_STARTS) else value


def _row(event: AuditEvent) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow(
        (
            event.occurred_at.isoformat(timespec="seconds"),
            event.actor.kind.value,
            _cell(event.actor.label),
            event.action.value,
            event.target.type,
            _cell(event.target.label),
            _cell("; ".join(f"{key}={value}" for key, value in event.details.items())),
        )
    )
    return buffer.getvalue()


@router.get(
    "/export",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_audit_log(
    container: ContainerDep,
    access: OrganizationAccessDep,
    category: Annotated[list[str] | None, Query()] = None,
    action: Annotated[list[AuditAction] | None, Query()] = None,
    actor_kind: Annotated[ActorKind | None, Query(alias="actorKind")] = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> StreamingResponse:
    """The whole filtered log as CSV (UTF-8 with a BOM, so spreadsheets read it)."""
    events = container.audit.export(access, _filter(category, action, actor_kind, since, until))

    async def lines() -> AsyncIterator[str]:
        header = io.StringIO()
        csv.writer(header).writerow(CSV_HEADER)
        yield "\ufeff" + header.getvalue()
        async for event in events:
            yield _row(event)

    stamp = f"{access.organization.alias}-audit.csv"
    return StreamingResponse(
        lines(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stamp}"'},
    )
