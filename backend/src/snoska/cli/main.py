from __future__ import annotations

import json

import typer
import uvicorn

from snoska.api.app import create_app
from snoska.bootstrap.settings import Settings
from snoska.cli import checks, corpus, db, demo, models, storage
from snoska.infrastructure.observability.logging import configure_logging
from snoska.infrastructure.observability.tracing import configure_tracing
from snoska.worker.runtime import WorkerRuntime

app = typer.Typer(help="Snoska platform commands.", no_args_is_help=True)
app.add_typer(db.app, name="db")
app.add_typer(corpus.app, name="corpus")
app.add_typer(models.app, name="models")
app.add_typer(demo.app, name="demo")
app.add_typer(checks.app, name="checks")
app.add_typer(storage.app, name="storage")


@app.command()
def api(reload: bool = False) -> None:
    """Serve the HTTP API."""
    settings = Settings()
    uvicorn.run(
        "snoska.api.asgi:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=reload,
        log_config=None,
        proxy_headers=True,
        server_header=False,
    )


@app.command()
def worker() -> None:
    """Run background jobs and the outbox relay."""
    settings = Settings()
    configure_logging(settings.observability.log_level, json=settings.observability.log_json)
    configure_tracing(
        "snoska-worker",
        settings.observability.tracing_exporter,
        settings.observability.otlp_endpoint,
    )
    WorkerRuntime(settings).run()


@app.command()
def openapi() -> None:
    """Print the OpenAPI document (source for the generated web client)."""
    typer.echo(json.dumps(create_app(Settings()).openapi(), ensure_ascii=False, indent=2))


def run() -> None:
    app()
