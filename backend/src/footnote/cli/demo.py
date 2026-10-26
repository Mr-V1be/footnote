from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from footnote.cli.demo_reset import reset_stand, run_nightly
from footnote.cli.demo_seed import apply_seed
from footnote.cli.support import container_scope, settings_for_cli
from footnote.infrastructure.demo.seed_file import read_seed

app = typer.Typer(help="Demo stand.", no_args_is_help=True)


@app.command()
def seed(file: Path | None = None) -> None:
    """Provision demo organizations, members and documents (idempotent)."""

    async def run() -> None:
        settings = settings_for_cli()
        data = read_seed(file or settings.demo_root / "seed.yaml")
        async with container_scope(settings) as container:
            await apply_seed(settings, container, data)

    asyncio.run(run())


@app.command()
def reset() -> None:
    """Return the demo stand to its seed now (FOOTNOTE_DEMO_MODE only)."""
    asyncio.run(reset_stand(settings_for_cli()))


@app.command()
def nightly() -> None:
    """Return the demo stand to its seed every night at FOOTNOTE_DEMO_RESET_HOUR."""
    asyncio.run(run_nightly(settings_for_cli()))
