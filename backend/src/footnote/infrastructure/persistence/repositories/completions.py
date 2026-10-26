from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from footnote.infrastructure.persistence.tables.operations import model_completions
from footnote.ports.ai import Completion
from footnote.ports.clock import Clock


class PostgresCompletionCache:
    """Model answers in PostgreSQL, valid for ``lifetime``: an answer older
    than that is asked again (models and the corpus move on)."""

    def __init__(self, engine: AsyncEngine, clock: Clock, lifetime: timedelta) -> None:
        self._engine = engine
        self._clock = clock
        self._lifetime = lifetime

    async def get(self, key: str) -> Completion | None:
        table = model_completions
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    select(table.c.model, table.c.text).where(
                        table.c.key == key,
                        table.c.created_at > self._clock.now() - self._lifetime,
                    )
                )
            ).first()
        if row is None:
            return None
        return Completion(
            text=row.text, model=row.model, prompt_tokens=None, completion_tokens=None
        )

    async def put(self, key: str, completion: Completion) -> None:
        table = model_completions
        statement = insert(table).values(
            key=key, model=completion.model, text=completion.text, created_at=self._clock.now()
        )
        async with self._engine.begin() as connection:
            await connection.execute(
                statement.on_conflict_do_update(
                    index_elements=[table.c.key],
                    set_={
                        "model": completion.model,
                        "text": completion.text,
                        "created_at": self._clock.now(),
                    },
                )
            )
