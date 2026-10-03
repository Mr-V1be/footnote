from __future__ import annotations

from typing import Protocol
from uuid import UUID


class TenantPurge(Protocol):
    """Removes every row of one tenant, append-only tables included. Only
    for resetting a demo stand: it runs with the schema owner's rights."""

    async def purge(self, organization_id: UUID) -> None: ...
