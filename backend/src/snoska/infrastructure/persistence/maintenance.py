"""Work across every tenant as the schema owner: removing a tenant's rows
(demo stand reset) and counting the background work still in progress."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from snoska.domain.checks.run import RunStatus
from snoska.domain.documents.version import ParseStatus
from snoska.ports.operations.maintenance import Backlog

# Tenant tables not reached by the cascade from `organizations` (append-only
# ones among them: the application role may not delete from those).
UNLINKED_TENANT_TABLES = (
    "conversations",
    "version_changes",
    "audit_events",
    "usage_ledger",
    "payment_events",
    "invoices",
    "subscriptions",
    "api_keys",
    "webhook_endpoints",
)


class OwnerTenantPurge:
    """Deletes one tenant in a single transaction: its pending jobs, the
    tables listed above, then the organization row, whose foreign keys
    cascade to workspaces, documents, versions, structures, checks and
    findings. The next access provisions the organization afresh."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def purge(self, organization_id: UUID) -> None:
        parameters = {"organization": str(organization_id)}
        async with self._engine.begin() as connection:
            await connection.execute(
                text(
                    "DELETE FROM outbox_messages WHERE dispatched_at IS NULL "
                    "AND payload->>'organization_id' = :organization"
                ),
                parameters,
            )
            for table in UNLINKED_TENANT_TABLES:
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE organization_id = :organization"),  # noqa: S608 - fixed table names
                    parameters,
                )
            await connection.execute(
                text("DELETE FROM organizations WHERE id = :organization"), parameters
            )


class OwnerBacklogProbe:
    """Counts unfinished work in every tenant at once: the schema owner is
    not bound by row-level security."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def backlog(self) -> Backlog:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT"
                        " (SELECT count(*) FROM outbox_messages WHERE dispatched_at IS NULL),"
                        " (SELECT count(*) FROM document_versions"
                        "   WHERE status IN (:queued_version, :parsing)),"
                        " (SELECT count(*) FROM check_runs"
                        "   WHERE status IN (:queued_run, :running))"
                    ),
                    {
                        "queued_version": ParseStatus.QUEUED.value,
                        "parsing": ParseStatus.PARSING.value,
                        "queued_run": RunStatus.QUEUED.value,
                        "running": RunStatus.RUNNING.value,
                    },
                )
            ).one()
        return Backlog(jobs=int(row[0]), versions=int(row[1]), checks=int(row[2]))
