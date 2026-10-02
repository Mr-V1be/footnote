from __future__ import annotations

import asyncio
import gzip

import httpx
import typer

from snoska.application.corpus.search import NormSearchQuery
from snoska.application.shared.jobs import EMBED_CORPUS_EDITION
from snoska.cli.support import container_scope, settings_for_cli
from snoska.infrastructure.corpus_sources.catalog import YamlActCatalog
from snoska.infrastructure.corpus_sources.pravo_ips import (
    SOURCE_CODE,
    PravoIpsClient,
    PravoIpsConfig,
    edition_from_html,
)
from snoska.infrastructure.system.clock import SystemClock

app = typer.Typer(help="Corpus of norms.", no_args_is_help=True)

DEFAULT_ACT = "152-fz"


@app.command()
def sync(
    act: str = DEFAULT_ACT,
    source: str = typer.Option("snapshot", help="snapshot | pravo_ips"),
    embed: bool = typer.Option(False, help="Embed right away instead of via the worker."),
) -> None:
    """Ingest the current redaction of an act as a new edition."""

    async def run() -> None:
        async with container_scope(settings_for_cli()) as container:
            result = await container.corpus_sync.sync(act, source)
            typer.echo(
                f"{result.act_code}: {result.outcome} edition={result.edition_id} "
                f"revision={result.source_revision} units={result.unit_count}"
            )
            if embed:
                handler = container.job_handlers[EMBED_CORPUS_EDITION.name]
                await handler({"edition_id": str(result.edition_id)})
                typer.echo("embedded and activated")

    asyncio.run(run())


@app.command()
def snapshot(act: str = DEFAULT_ACT) -> None:
    """Download the current portal text into the bundled snapshot."""

    async def run() -> None:
        settings = settings_for_cli()
        catalog = YamlActCatalog(settings.corpus_catalog)
        entry = catalog.entry(act)
        reference = entry.tracked.source_refs.get(SOURCE_CODE)
        if entry.snapshot is None or reference is None:
            raise typer.BadParameter(f"{act} has no snapshot or portal reference")
        async with httpx.AsyncClient() as http:
            raw = await PravoIpsClient(http, PravoIpsConfig()).fetch(reference)
        edition = edition_from_html(raw, SystemClock().now())
        entry.snapshot.path.write_bytes(gzip.compress(raw.html, mtime=0))
        typer.echo(
            f"saved {entry.snapshot.path.name}: revision={raw.revision} "
            f"amended_by={edition.amended_by}; update `revision` and `retrieved_at` in acts.yaml"
        )

    asyncio.run(run())


@app.command()
def search(query: str, act: str | None = None, limit: int = 5) -> None:
    """Semantic search over the active editions."""

    async def run() -> None:
        async with container_scope(settings_for_cli()) as container:
            hits = await container.norm_search.search(
                NormSearchQuery(text=query, act_code=act, limit=limit)
            )
            for hit in hits:
                typer.echo(f"{1 - hit.distance:.3f}  {hit.unit.citation}  {hit.unit.text[:140]}")

    asyncio.run(run())
