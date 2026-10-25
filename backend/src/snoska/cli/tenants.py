"""Customers' organizations and the platform's operators (production)."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from snoska.application.tenancy.onboarding import Onboarding, Person
from snoska.cli.support import container_scope, settings_for_cli
from snoska.domain.shared.locale import SOURCE_LOCALE, Locale

app = typer.Typer(help="Organizations and platform operators.", no_args_is_help=True)


@app.command()
def create(
    alias: Annotated[str, typer.Argument(help="Short name in addresses, e.g. romashka.")],
    name: Annotated[str, typer.Option(help="Full name, e.g. ООО «Ромашка».")],
    domain: Annotated[str, typer.Option(help="The organization's mail domain.")],
    owner_email: Annotated[str, typer.Option()],
    owner_first_name: Annotated[str, typer.Option()],
    owner_last_name: Annotated[str, typer.Option()],
    owner_locale: Annotated[
        Locale, typer.Option(help="The language of the owner's invitation.")
    ] = SOURCE_LOCALE,
) -> None:
    """Open an organization; its owner gets an invitation mail to set a password."""
    settings = settings_for_cli()
    owner = Person(owner_email, owner_first_name, owner_last_name, owner_locale)

    async def run() -> None:
        async with container_scope(settings) as container:
            onboarding = Onboarding(container.provisioning, container.administration)
            profile = await onboarding.open_organization(alias, name, domain, owner)
        typer.echo(f"{profile.alias}: opened, invitation sent to {owner.email}")

    asyncio.run(run())


@app.command()
def operator(
    email: Annotated[str, typer.Option()],
    first_name: Annotated[str, typer.Option()],
    last_name: Annotated[str, typer.Option()],
    password: Annotated[str, typer.Option(prompt=True, hide_input=True, confirmation_prompt=True)],
) -> None:
    """Add a platform operator (the password is asked, never echoed)."""
    settings = settings_for_cli()

    async def run() -> None:
        async with container_scope(settings) as container:
            onboarding = Onboarding(container.provisioning, container.administration)
            await onboarding.add_operator(
                Person(email, first_name, last_name),
                password,
                settings.operations.platform_admin_role,
            )
        typer.echo(f"{email}: platform operator")

    asyncio.run(run())
