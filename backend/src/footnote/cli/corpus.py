from __future__ import annotations

import asyncio
import gzip

import httpx
import typer

from footnote.application.corpus.search import NormSearchQuery
from footnote.cli.support import container_scope, owner_engine, settings_for_cli
from footnote.infrastructure.corpus_sources.catalog import YamlActCatalog
from footnote.infrastructure.corpus_sources.pravo_ips import (
    SOURCE_CODE,
    PravoIpsClient,
    PravoIpsConfig,
    edition_from_html,
)
from footnote.infrastructure.persistence.vector_index import drop_spaces_except, ensure_space
from footnote.infrastructure.system.clock import SystemClock

app = typer.Typer(help="Corpus of norms.", no_args_is_help=True)

DEFAULT_ACT = "152-fz"


@app.command()
def sync(
    act: str = DEFAULT_ACT,
    source: str = typer.Option("snapshot", help="snapshot | pravo_ips"),
) -> None:
    """Ingest the current redaction of an act as the edition in force.

    The edition is indexed for search by the worker, or by `reindex`.
    """

    async def run() -> None:
        async with container_scope(settings_for_cli()) as container:
            result = await container.corpus_sync.sync(act, source)
            typer.echo(
                f"{result.act_code}: {result.outcome} edition={result.edition_id} "
                f"revision={result.source_revision} units={result.unit_count}"
            )

    asyncio.run(run())


@app.command()
def reindex(
    prune: bool = typer.Option(False, help="Drop vectors and indexes of other models."),
) -> None:
    """Embed the editions in force with the configured embedding model.

    Registers the model's vector space with its search index (as the schema
    owner), embeds what is missing and marks each edition searchable. Run it
    after configuring or changing the embedding model or its vector size.
    """

    async def run() -> None:
        settings = settings_for_cli()
        space = settings.ai.embedding_space()
        if space.dimensions <= 0:
            raise typer.BadParameter("configure SNOSKA_EMBEDDING_MODEL and _DIMENSIONS first")
        engine = owner_engine(settings)
        try:
            await ensure_space(engine, space)
            if prune:
                dropped = await drop_spaces_except(engine, space)
                typer.echo(f"dropped spaces: {', '.join(dropped) or 'none'}")
        finally:
            await engine.dispose()
        async with container_scope(settings) as container:
            embedded = await container.corpus_indexing.reindex_active()
        for edition_id, count in embedded.items():
            typer.echo(f"edition {edition_id}: indexed in {space.code}, {count} passages embedded")

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


@app.command()
def watch() -> None:
    """Check the official portal for new redactions now (as the weekly job does)."""

    async def run() -> None:
        async with container_scope(settings_for_cli()) as container:
            checks = await container.corpus_watch.run()
        for check in checks:
            typer.echo(f"{check.act_code}: {check.outcome} {check.revision or check.error or ''}")

    asyncio.run(run())
