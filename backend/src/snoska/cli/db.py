from __future__ import annotations

import typer
from alembic import command
from alembic.config import Config

from snoska.bootstrap.settings import BACKEND_ROOT

app = typer.Typer(help="Database schema.", no_args_is_help=True)


def _alembic() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


@app.command()
def migrate(revision: str = "head") -> None:
    """Apply migrations (runs as the schema owner)."""
    command.upgrade(_alembic(), revision)


@app.command()
def current() -> None:
    """Show the applied revision."""
    command.current(_alembic())
