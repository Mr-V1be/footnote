from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footnote.domain.shared.locale import Locale
from footnote.domain.tenancy.organization import Organization, UserProfile, Workspace
from footnote.domain.tenancy.workspace_access import WorkspaceMember


class OrganizationRepository(Protocol):
    async def get(self, organization_id: UUID) -> Organization | None: ...

    async def get_by_alias(self, alias: str) -> Organization | None: ...

    async def add_if_absent(self, organization: Organization) -> None: ...

    async def list_all(self, *, limit: int, offset: int) -> Sequence[Organization]: ...


class WorkspaceRepository(Protocol):
    """Tenant-scoped: sees only the workspaces of the current organization."""

    async def list(self) -> Sequence[Workspace]: ...

    async def get(self, workspace_id: UUID) -> Workspace | None: ...

    async def get_by_slug(self, slug: str) -> Workspace | None: ...

    async def add_if_absent(self, workspace: Workspace) -> None: ...

    async def add(self, workspace: Workspace) -> None:
        """Raise SlugTakenError when the organization already has the slug."""
        ...

    async def save(self, workspace: Workspace) -> None: ...

    async def delete(self, workspace_id: UUID) -> None: ...

    async def document_counts(self) -> Mapping[UUID, int]: ...


class WorkspaceMemberRepository(Protocol):
    """Roles given inside workspaces; tenant-scoped."""

    async def list_for_workspace(self, workspace_id: UUID) -> Sequence[WorkspaceMember]: ...

    async def list_for_user(self, user_id: UUID) -> Sequence[WorkspaceMember]: ...

    async def get(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None: ...

    async def put(self, member: WorkspaceMember) -> None: ...

    async def remove(self, workspace_id: UUID, user_id: UUID) -> None: ...

    async def remove_user(self, user_id: UUID) -> None:
        """When someone leaves the organization."""
        ...


class UserProfileRepository(Protocol):
    async def upsert(self, profile: UserProfile, now: datetime) -> None: ...

    async def get_many(self, user_ids: Sequence[UUID]) -> Mapping[UUID, UserProfile]: ...

    async def remember_locale(self, user_id: UUID, locale: Locale) -> None:
        """The interface language a person uses now, for mail sent to them
        (the profile exists: it is written first)."""
        ...

    async def locales(self, user_ids: Collection[UUID]) -> Mapping[UUID, Locale]:
        """The interface languages people last used; those never seen are left out."""
        ...
