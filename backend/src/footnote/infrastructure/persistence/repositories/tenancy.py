from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from footnote.domain.shared.locale import Locale, parse_locale
from footnote.domain.tenancy.organization import (
    Organization,
    SlugTakenError,
    UserProfile,
    Workspace,
)
from footnote.domain.tenancy.workspace_access import WorkspaceMember
from footnote.infrastructure.persistence.tables.documents import documents
from footnote.infrastructure.persistence.tables.tenancy import (
    organizations,
    user_profiles,
    workspace_members,
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
        restricted=row["restricted"],
    )


def _member(row: RowMapping) -> WorkspaceMember:
    return WorkspaceMember(
        workspace_id=row["workspace_id"],
        user_id=row["user_id"],
        role_code=row["role_code"],
        added_at=row["added_at"],
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

    async def get_by_alias(self, alias: str) -> Organization | None:
        result = await self._connection.execute(
            select(organizations).where(organizations.c.alias == alias)
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

    async def add(self, workspace: Workspace) -> None:
        statement = (
            insert(workspaces)
            .values(
                id=workspace.id,
                organization_id=workspace.organization_id,
                slug=workspace.slug,
                name=workspace.name,
                created_at=workspace.created_at,
                restricted=workspace.restricted,
            )
            .on_conflict_do_nothing(
                index_elements=[workspaces.c.organization_id, workspaces.c.slug]
            )
            .returning(workspaces.c.id)
        )
        if (await self._connection.execute(statement)).first() is None:
            raise SlugTakenError(f"workspace {workspace.slug!r} already exists")

    async def save(self, workspace: Workspace) -> None:
        try:
            await self._connection.execute(
                update(workspaces)
                .where(workspaces.c.id == workspace.id)
                .values(slug=workspace.slug, name=workspace.name, restricted=workspace.restricted)
            )
        except IntegrityError as exc:
            raise SlugTakenError(f"workspace {workspace.slug!r} already exists") from exc

    async def delete(self, workspace_id: UUID) -> None:
        await self._connection.execute(delete(workspaces).where(workspaces.c.id == workspace_id))

    async def document_counts(self) -> Mapping[UUID, int]:
        result = await self._connection.execute(
            select(documents.c.workspace_id, func.count()).group_by(documents.c.workspace_id)
        )
        return {row[0]: int(row[1]) for row in result}


class SqlWorkspaceMemberRepository:
    def __init__(self, connection: AsyncConnection, organization_id: UUID | None) -> None:
        self._connection = connection
        self._organization_id = organization_id

    async def list_for_workspace(self, workspace_id: UUID) -> Sequence[WorkspaceMember]:
        result = await self._connection.execute(
            select(workspace_members)
            .where(workspace_members.c.workspace_id == workspace_id)
            .order_by(workspace_members.c.added_at)
        )
        return [_member(row) for row in result.mappings()]

    async def list_for_user(self, user_id: UUID) -> Sequence[WorkspaceMember]:
        result = await self._connection.execute(
            select(workspace_members).where(workspace_members.c.user_id == user_id)
        )
        return [_member(row) for row in result.mappings()]

    async def get(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        result = await self._connection.execute(
            select(workspace_members).where(
                workspace_members.c.workspace_id == workspace_id,
                workspace_members.c.user_id == user_id,
            )
        )
        row = result.mappings().first()
        return _member(row) if row else None

    async def put(self, member: WorkspaceMember) -> None:
        if self._organization_id is None:
            raise RuntimeError("workspace members are written in a tenant unit of work")
        statement = insert(workspace_members).values(
            organization_id=self._organization_id,
            workspace_id=member.workspace_id,
            user_id=member.user_id,
            role_code=member.role_code,
            added_at=member.added_at,
        )
        await self._connection.execute(
            statement.on_conflict_do_update(
                index_elements=[workspace_members.c.workspace_id, workspace_members.c.user_id],
                set_={"role_code": statement.excluded.role_code},
            )
        )

    async def remove(self, workspace_id: UUID, user_id: UUID) -> None:
        await self._connection.execute(
            delete(workspace_members).where(
                workspace_members.c.workspace_id == workspace_id,
                workspace_members.c.user_id == user_id,
            )
        )

    async def remove_user(self, user_id: UUID) -> None:
        await self._connection.execute(
            delete(workspace_members).where(workspace_members.c.user_id == user_id)
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

    async def get_many(self, user_ids: Sequence[UUID]) -> Mapping[UUID, UserProfile]:
        if not user_ids:
            return {}
        result = await self._connection.execute(
            select(user_profiles).where(user_profiles.c.id.in_(list(user_ids)))
        )
        return {
            row["id"]: UserProfile(
                id=row["id"], email=row["email"], display_name=row["display_name"]
            )
            for row in result.mappings()
        }

    async def remember_locale(self, user_id: UUID, locale: Locale) -> None:
        await self._connection.execute(
            update(user_profiles)
            .where(
                user_profiles.c.id == user_id,
                user_profiles.c.locale.is_distinct_from(locale.value),
            )
            .values(locale=locale.value)
        )

    async def locales(self, user_ids: Collection[UUID]) -> Mapping[UUID, Locale]:
        if not user_ids:
            return {}
        result = await self._connection.execute(
            select(user_profiles.c.id, user_profiles.c.locale).where(
                user_profiles.c.id.in_(list(user_ids)), user_profiles.c.locale.is_not(None)
            )
        )
        found = {row.id: parse_locale(row.locale) for row in result}
        return {user_id: locale for user_id, locale in found.items() if locale is not None}
