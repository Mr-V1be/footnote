from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from snoska.domain.tenancy.organization import Organization, UserProfile, Workspace
from snoska.infrastructure.persistence.tables.tenancy import (
    organizations,
    user_profiles,
    workspaces,
)


def _organization(row: RowMapping) -> Organization:
    return Organization(
        id=row["id"], alias=row["alias"], name=row["name"], created_at=row["created_at"]
    )


def _workspace(row: RowMapping) -> Workspace:
    return Workspace(
        id=row["id"],
        organization_id=row["organization_id"],
        slug=row["slug"],
        name=row["name"],
        created_at=row["created_at"],
    )


class SqlOrganizationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get(self, organization_id: UUID) -> Organization | None:
        result = await self._connection.execute(
            select(organizations).where(organizations.c.id == organization_id)
        )
        row = result.mappings().first()
        return _organization(row) if row else None

    async def add_if_absent(self, organization: Organization) -> None:
        await self._connection.execute(
            insert(organizations)
            .values(
                id=organization.id,
                alias=organization.alias,
                name=organization.name,
                created_at=organization.created_at,
            )
            .on_conflict_do_nothing(index_elements=[organizations.c.id])
        )

    async def list_all(self, *, limit: int, offset: int) -> Sequence[Organization]:
        result = await self._connection.execute(
            select(organizations).order_by(organizations.c.name).limit(limit).offset(offset)
        )
        return [_organization(row) for row in result.mappings()]


class SqlWorkspaceRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def list(self) -> Sequence[Workspace]:
        result = await self._connection.execute(
            select(workspaces).order_by(workspaces.c.created_at, workspaces.c.id)
        )
        return [_workspace(row) for row in result.mappings()]

    async def get(self, workspace_id: UUID) -> Workspace | None:
        result = await self._connection.execute(
            select(workspaces).where(workspaces.c.id == workspace_id)
        )
        row = result.mappings().first()
        return _workspace(row) if row else None

    async def get_by_slug(self, slug: str) -> Workspace | None:
        result = await self._connection.execute(select(workspaces).where(workspaces.c.slug == slug))
        row = result.mappings().first()
        return _workspace(row) if row else None

    async def add_if_absent(self, workspace: Workspace) -> None:
        await self._connection.execute(
            insert(workspaces)
            .values(
                id=workspace.id,
                organization_id=workspace.organization_id,
                slug=workspace.slug,
                name=workspace.name,
                created_at=workspace.created_at,
            )
            .on_conflict_do_nothing(
                index_elements=[workspaces.c.organization_id, workspaces.c.slug]
            )
        )


class SqlUserProfileRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def upsert(self, profile: UserProfile, now: datetime) -> None:
        statement = insert(user_profiles).values(
            id=profile.id,
            email=profile.email,
            display_name=profile.display_name,
            updated_at=now,
        )
        excluded = statement.excluded
        await self._connection.execute(
            statement.on_conflict_do_update(
                index_elements=[user_profiles.c.id],
                set_={
                    "email": excluded.email,
                    "display_name": excluded.display_name,
                    "updated_at": excluded.updated_at,
                },
                # Skip the write entirely when nothing changed.
                where=(
                    user_profiles.c.email.is_distinct_from(excluded.email)
                    | user_profiles.c.display_name.is_distinct_from(excluded.display_name)
                ),
            )
        )
