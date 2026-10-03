"""Organization set-up of the demo stand beyond members and documents:
workspaces with their own roles, the plan, an API key and a webhook to the
stand's own receiver. Every step is idempotent, like the rest of the seed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import typer

from snoska.application.integrations.webhooks import EndpointSpec
from snoska.bootstrap.container import Container
from snoska.domain.integrations.api_keys import ApiScope
from snoska.domain.integrations.webhooks import WebhookEvent
from snoska.domain.tenancy.access import Actor, ActorKind, OrganizationAccess, Principal

DEMO_ACTOR = Actor(kind=ActorKind.SYSTEM, id=None, label="demo seed")


async def ensure_workspaces(
    container: Container,
    access: OrganizationAccess,
    alias: str,
    workspaces: list[dict[str, Any]],
    members: Mapping[str, Principal],
) -> None:
    existing = {
        item.access.workspace.slug: item.access.workspace
        for item in await container.workspaces.list(access)
    }
    for spec in workspaces:
        workspace = existing.get(spec["slug"])
        if workspace is None:
            workspace = await container.workspaces.create(
                access,
                name=spec["name"],
                slug=spec["slug"],
                restricted=spec.get("restricted", False),
            )
            typer.echo(f"{alias}: workspace {spec['slug']} created")
        assigned = {
            entry.user_id: entry.role_code
            for entry in await container.workspaces.members(access, workspace.id)
        }
        for entry in spec.get("members", []):
            person = members[entry["email"]]
            if assigned.get(person.user_id) == entry["role"]:
                continue
            await container.workspaces.set_member(
                access,
                workspace.id,
                user_id=person.user_id,
                label=person.display_name,
                role_code=entry["role"],
            )
            typer.echo(f"{alias}: {entry['email']} is {entry['role']} in {spec['slug']}")


async def ensure_plan(container: Container, organization_id: UUID, alias: str, plan: str) -> None:
    subscription, _ = await container.billing.usage_of(organization_id)
    if subscription.plan_code != plan:
        await container.billing.assign(organization_id, plan, DEMO_ACTOR)
    typer.echo(f"{alias}: plan {plan}")


async def ensure_integrations(
    container: Container,
    access: OrganizationAccess,
    alias: str,
    spec: dict[str, Any],
    api_url: str,
) -> None:
    keys = await container.api_keys.list(access)
    for key in spec.get("api_keys", []):
        if any(item.name == key["name"] and item.revoked_at is None for item in keys):
            continue
        await container.api_keys.create(
            access, name=key["name"], scopes=frozenset(ApiScope(scope) for scope in key["scopes"])
        )
        typer.echo(f"{alias}: API key «{key['name']}» created (its token is not kept)")
    endpoints = await container.webhooks.list(access)
    for hook in spec.get("webhooks", []):
        if any(item.description == hook["description"] for item in endpoints):
            continue
        events = frozenset(WebhookEvent(event) for event in hook["events"])
        # The stand's own receiver checks signatures with the endpoint's secret,
        # so its address carries the endpoint's id, known once it exists.
        receiver = f"{api_url}/api/v1/demo/webhooks/{alias}"
        endpoint = await container.webhooks.create(
            access, EndpointSpec(url=receiver, description=hook["description"], events=events)
        )
        await container.webhooks.update(
            access,
            endpoint.id,
            EndpointSpec(
                url=f"{receiver}/{endpoint.id}", description=hook["description"], events=events
            ),
        )
        await container.webhooks.ping(access, endpoint.id)
        typer.echo(f"{alias}: webhook «{hook['description']}» to the demo receiver")
