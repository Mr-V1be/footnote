from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from snoska.bootstrap.container import load_check_catalog
from snoska.cli.quality_markdown import render
from snoska.cli.support import container_scope, settings_for_cli
from snoska.domain.checks.quality import DocumentTiming, QualityReport
from snoska.domain.documents.formats import SUPPORTED_FORMATS
from snoska.infrastructure.checks.quality_store import (
    JsonModelTrialStore,
    JsonQualityReportStore,
)
from snoska.infrastructure.checks.reference import YamlReferenceSet

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
    only: Annotated[
        str, typer.Option(help="Measure only these reference files, comma-separated.")
    ] = "",
    trial: Annotated[
        bool, typer.Option(help="Keep the result as a trial of the configured model.")
    ] = False,
    model: Annotated[
        str, typer.Option(help="Try this model instead of the configured one, without fallbacks.")
    ] = "",
) -> None:
    """Measure the checks on the labelled reference set (precision, recall, time).

    With --trial the result is kept apart, one per model, to choose the model
    the product runs on; the main measurement stays as it was.
    """
    settings = settings_for_cli()
    if model:
        # A trial measures one model: no other model may answer in its place.
        ai = settings.ai.model_copy(update={"llm_model": model, "llm_fallback_models": ""})
        settings = settings.model_copy(update={"ai": ai})
    files = frozenset(item.strip() for item in only.split(",") if item.strip())

    async def run() -> QualityReport:
        async with container_scope(settings) as container:
            store = JsonModelTrialStore(settings.checks.model_trials) if trial else None
            return await container.benchmark.run(
                on_document=_echo_document, only=files, store=store
            )

    report = asyncio.run(run())
    for method, metrics in report.by_method().items():
        typer.echo(
            f"{method.value}: precision {metrics.precision}, recall {metrics.recall}, "
            f"not run {metrics.errors}"
        )
    target = settings.checks.model_trials if trial else settings.checks.quality_report
    typer.echo(f"saved to {target}")
    if markdown is not None:
        trials = JsonModelTrialStore(settings.checks.model_trials).all()
        rendered = render(report, load_check_catalog(settings.checks), trials)
        markdown.write_text(rendered, "utf-8")
        typer.echo(f"written {markdown}")


@app.command()
def adopt(
    model: Annotated[str, typer.Argument(help="The model whose trial becomes the measurement.")],
    markdown: Annotated[
        Path | None, typer.Option(help="Also write the result as Markdown here.")
    ] = None,
) -> None:
    """Make a model's trial on the whole reference set the published measurement.

    A trial records real request times; a later run of the same requests is
    answered from the cache and would not, so the chosen model's trial is
    published as it was measured.
    """
    settings = settings_for_cli()
    trials = JsonModelTrialStore(settings.checks.model_trials).all()
    total = len(YamlReferenceSet(settings.checks.reference_dir, SUPPORTED_FORMATS).documents())
    chosen = next(
        (trial for trial in trials if trial.model == model and len(trial.documents) == total),
        None,
    )
    if chosen is None:
        raise typer.BadParameter(f"no trial of {model} on all {total} reference documents")
    JsonQualityReportStore(settings.checks.quality_report).save(chosen)
    typer.echo(f"{model}: published to {settings.checks.quality_report}")
    if markdown is not None:
        rendered = render(chosen, load_check_catalog(settings.checks), trials)
        markdown.write_text(rendered, "utf-8")
        typer.echo(f"written {markdown}")
