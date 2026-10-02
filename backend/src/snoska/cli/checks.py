from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from snoska.bootstrap.container import load_check_catalog
from snoska.cli.quality_markdown import render
from snoska.cli.support import container_scope, settings_for_cli
from snoska.domain.checks.quality import DocumentTiming, QualityReport

app = typer.Typer(help="Document checks.", no_args_is_help=True)


@app.command()
def recheck() -> None:
    """Queue a check of every document's latest version (after catalogue changes)."""

    async def run() -> None:
        async with container_scope(settings_for_cli()) as container:
            scheduled = await container.recheck.all_organizations()
        for alias, count in scheduled.items():
            typer.echo(f"{alias}: {count} documents queued")

    asyncio.run(run())


def _seconds(milliseconds: int | None) -> str:
    return "not measured" if milliseconds is None else f"{milliseconds / 1000:.2f}s"


def _echo_document(timing: DocumentTiming) -> None:
    typer.echo(
        f"{timing.file_name}: parse {_seconds(timing.parse_ms)}, "
        f"rules {_seconds(timing.deterministic_ms)}, model {_seconds(timing.model_ms)}"
    )


@app.command()
def benchmark(
    markdown: Annotated[
        Path | None, typer.Option(help="Also write the result as Markdown here.")
    ] = None,
) -> None:
    """Measure the checks on the labelled reference set (precision, recall, time)."""
    settings = settings_for_cli()

    async def run() -> QualityReport:
        async with container_scope(settings) as container:
            return await container.benchmark.run(on_document=_echo_document)

    report = asyncio.run(run())
    for method, metrics in report.by_method().items():
        typer.echo(
            f"{method.value}: precision {metrics.precision}, recall {metrics.recall}, "
            f"not run {metrics.errors}"
        )
    typer.echo(f"saved to {settings.checks.quality_report}")
    if markdown is not None:
        markdown.write_text(render(report, load_check_catalog(settings.checks)), "utf-8")
        typer.echo(f"written {markdown}")
