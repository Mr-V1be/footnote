"""The nightly return of the demo stand to its seed."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import anyio
import structlog
import typer

from snoska.application.operations.demo_reset import DemoStandReset
from snoska.bootstrap.settings import Settings
from snoska.cli.demo_seed import apply_seed
from snoska.cli.support import container_scope, owner_engine
from snoska.infrastructure.demo.seed_file import read_seed
from snoska.infrastructure.persistence.maintenance import OwnerTenantPurge

log = structlog.get_logger(__name__)


def seeded_emails(organization: dict[str, Any]) -> frozenset[str]:
    return frozenset(str(member["email"]).casefold() for member in organization["members"])


async def reset_stand(settings: Settings) -> None:
    """Clear every seeded organization, then seed the stand again."""
    if not settings.demo.mode:
        raise typer.BadParameter(
            "the reset clears the seeded organizations: it runs only with SNOSKA_DEMO_MODE=true"
        )
    data = read_seed(settings.demo_root / "seed.yaml")
    engine = owner_engine(settings)
    try:
        async with container_scope(settings) as container:
            reset = DemoStandReset(
                OwnerTenantPurge(engine),
                container.blobs,
                container.directory,
                container.administration,
            )
            for organization in data["organizations"]:
                profile = await container.provisioning.ensure_organization(
                    organization["alias"], organization["name"], organization["domain"]
                )
                cleared = await reset.clear(profile.id, seeded_emails(organization))
                typer.echo(
                    f"{organization['alias']}: cleared, {cleared.files} files, "
                    f"{cleared.removed_members} added members removed"
                )
            await apply_seed(settings, container, data)
    finally:
        await engine.dispose()
    log.info("demo.reset", organizations=len(data["organizations"]))


def next_reset(now: datetime, hour: int) -> datetime:
    """The next moment at ``hour`` o'clock in ``now``'s time zone."""
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(days=1)


async def run_nightly(settings: Settings) -> None:
    """Sleep until the reset hour, reset, repeat: the stand's scheduled task."""
    zone = ZoneInfo(settings.demo.timezone)
    while True:
        now = datetime.now(zone)
        due = next_reset(now, settings.demo.reset_hour)
        log.info("demo.reset_scheduled", at=due.isoformat())
        await anyio.sleep((due - now).total_seconds())
        try:
            await reset_stand(settings)
        except Exception:  # the schedule outlives one failed night
            log.exception("demo.reset_failed")
