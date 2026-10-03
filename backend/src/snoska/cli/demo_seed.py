"""Applying the seed file to the stand."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import anyio
import typer

from snoska.application.documents.upload import IncomingFile
from snoska.bootstrap.container import Container
from snoska.bootstrap.settings import Settings
from snoska.cli.demo_setup import ensure_integrations, ensure_plan, ensure_workspaces
from snoska.domain.tenancy.access import MembershipClaim, Principal
from snoska.domain.tenancy.roles import ORGANIZATION_ROLES, OWNER_ROLE
from snoska.ports.identity import MemberSpec

READ_CHUNK_BYTES = 256 * 1024


async def _file_chunks(path: Path) -> AsyncIterator[bytes]:
    async with await anyio.open_file(path, "rb") as handle:
        while chunk := await handle.read(READ_CHUNK_BYTES):
            yield chunk


def _state(created: bool) -> str:
    return "uploaded" if created else "already present"


def _display_name(member: dict[str, Any]) -> str:
    return f"{member['first_name']} {member['last_name']}"


async def apply_seed(settings: Settings, container: Container, data: dict[str, Any]) -> None:
    """Make the stand match the seed: organizations, members with their roles
    and passwords, workspaces, plans, documents and integrations (idempotent)."""
    role_codes = tuple(role.code for role in ORGANIZATION_ROLES.all())
    provisioning = container.provisioning
    admin = data["platform_admin"]
    await provisioning.ensure_platform_user(
        admin["email"],
        admin["first_name"],
        admin["last_name"],
        admin["password"],
        admin["realm_role"],
    )
    typer.echo(f"platform admin: {admin['email']}")
    for organization in data["organizations"]:
        alias = organization["alias"]
        profile = await provisioning.ensure_organization(
            alias, organization["name"], organization["domain"]
        )
        await provisioning.ensure_role_groups(profile.id, role_codes)
        members: dict[str, Principal] = {}
        for member in organization["members"]:
            user_id = await provisioning.ensure_member(
                profile.id,
                MemberSpec(
                    email=member["email"],
                    first_name=member["first_name"],
                    last_name=member["last_name"],
                    password=member["password"],
                    role_code=member["role"],
                ),
            )
            members[member["email"]] = Principal(
                user_id=user_id,
                email=member["email"],
                display_name=_display_name(member),
                memberships=(
                    MembershipClaim(
                        organization_id=profile.id,
                        organization_alias=alias,
                        role_codes=frozenset({member["role"]}),
                    ),
                ),
                platform_role_codes=frozenset(),
            )
            typer.echo(f"{alias}: {member['email']} ({member['role']})")
        owner = next(
            members[member["email"]]
            for member in organization["members"]
            if member["role"] == OWNER_ROLE
        )
        owner_access = await container.tenant_access.organization_access(owner, alias)
        await ensure_workspaces(
            container, owner_access, alias, organization.get("workspaces", []), members
        )
        if "plan" in organization:
            await ensure_plan(container, profile.id, alias, organization["plan"])
        uploaded: dict[str, UUID] = {}
        for document in organization.get("documents", []):
            uploader = members[document["uploaded_by"]]
            access = await container.tenant_access.organization_access(uploader, alias)
            path = settings.demo_root / document["file"]
            result = await container.uploads.upload_document(
                access,
                uploader.profile,
                workspace_slug=document.get("workspace", settings.tenancy.default_workspace_slug),
                incoming=IncomingFile(filename=path.name, chunks=_file_chunks(path)),
                kind_code=document["kind"],
                title=document.get("title"),
                upload_key=f"demo-seed:{alias}:{document['file']}",
            )
            uploaded[document["file"]] = result.document_id
            typer.echo(f"{alias}: {path.name} {_state(result.created)}")
        for version in organization.get("versions", []):
            uploader = members[version["uploaded_by"]]
            access = await container.tenant_access.organization_access(uploader, alias)
            path = settings.demo_root / version["file"]
            result = await container.uploads.upload_version(
                access,
                uploader.profile,
                document_id=uploaded[version["document"]],
                incoming=IncomingFile(filename=path.name, chunks=_file_chunks(path)),
                upload_key=f"demo-seed:{alias}:{version['file']}",
            )
            state = _state(result.created)
            typer.echo(f"{alias}: {path.name} v{result.version_number} {state}")
        if "integrations" in organization:
            await ensure_integrations(
                container,
                owner_access,
                alias,
                organization["integrations"],
                settings.api_url,
            )
