from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from snoska.domain.tenancy.organization import Organization, UserProfile, Workspace


class OrganizationRepository(Protocol):
    async def get(self, organization_id: UUID) -> Organization | None: ...

    async def add_if_absent(self, organization: Organization) -> None: ...

    async def list_all(self, *, limit: int, offset: int) -> Sequence[Organization]: ...


class WorkspaceRepository(Protocol):
    """Tenant-scoped: sees only the workspaces of the current organization."""

    async def list(self) -> Sequence[Workspace]: ...

    async def get(self, workspace_id: UUID) -> Workspace | None: ...

    async def get_by_slug(self, slug: str) -> Workspace | None: ...

    async def add_if_absent(self, workspace: Workspace) -> None: ...


class UserProfileRepository(Protocol):
    async def upsert(self, profile: UserProfile, now: datetime) -> None: ...
