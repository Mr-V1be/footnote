"""Removing a tenant's rows as the schema owner (demo stand reset)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

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
