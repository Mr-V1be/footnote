"""Migrations run as the schema owner; the runtime role only receives grants."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from snoska.bootstrap.settings import Settings
from snoska.infrastructure.persistence.database import DatabaseConfig, create_engine
from snoska.infrastructure.persistence.tables import metadata

target_metadata = metadata


SETTINGS = Settings()
# Migrations grant table privileges to the runtime role by its configured name.
context.config.attributes["app_role"] = SETTINGS.database.app_user


def _owner_config() -> DatabaseConfig:
    db = SETTINGS.database
    return DatabaseConfig(
        host=db.host,
        port=db.port,
        name=db.name,
        user=db.owner_user,
        password=db.owner_password.get_secret_value(),
        pool_size=1,
        max_overflow=0,
        statement_timeout_ms=0,
    )


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = create_engine(_owner_config())
    async with engine.connect() as connection:
        await connection.run_sync(_run)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline migrations are not supported")
asyncio.run(_run_async())
