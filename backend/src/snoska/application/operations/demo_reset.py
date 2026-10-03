from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from snoska.ports.blob_storage import BlobStorage
from snoska.ports.identity import MemberAdministration, OrganizationDirectory
from snoska.ports.operations.maintenance import TenantPurge


@dataclass(frozen=True, slots=True)
class ClearedTenant:
    files: int
    removed_members: int


class DemoStandReset:
    """Returns a seeded organization of the demo stand to nothing, before the
    seed fills it again: its rows, its files and the members visitors added.
    The seeded members stay (the seed restores their roles and passwords)."""

    def __init__(
        self,
        purge: TenantPurge,
        blobs: BlobStorage,
        directory: OrganizationDirectory,
        administration: MemberAdministration,
    ) -> None:
        self._purge = purge
        self._blobs = blobs
        self._directory = directory
        self._administration = administration

    async def clear(self, organization_id: UUID, seeded_emails: frozenset[str]) -> ClearedTenant:
        files = [key async for key in self._blobs.keys(f"tenants/{organization_id}/")]
        await self._purge.purge(organization_id)
        for key in files:
            await self._blobs.delete(key)
        extra = [
            member
            for member in await self._directory.list_members(organization_id)
            if (member.email or "").casefold() not in seeded_emails
        ]
        for member in extra:
            await self._administration.remove(organization_id, member.user_id)
        return ClearedTenant(files=len(files), removed_members=len(extra))
