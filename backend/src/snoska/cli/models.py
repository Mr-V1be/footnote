from __future__ import annotations

import asyncio
import json
import time

import typer

from snoska.cli.support import container_scope, settings_for_cli
from snoska.ports.ai import ChatMessage, CompletionRequest, MessageRole

app = typer.Typer(help="Language model and embedding providers.", no_args_is_help=True)

_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"article": {"type": "string"}, "summary": {"type": "string"}},
    "required": ["article", "summary"],
    "additionalProperties": False,
}


@app.command()
def check() -> None:
    """Verify that the configured models answer, including structured output."""

    async def run() -> None:
        async with container_scope(settings_for_cli()) as container:
            ai = container.ai
            started = time.perf_counter()
            [vector] = await ai.embedder.embed(["Согласие на обработку персональных данных"])
            ai.embedder.space.validate(vector)
            typer.echo(
                f"embedder {ai.embedder.model}: {len(vector)} dims, "
                f"{time.perf_counter() - started:.2f}s"
            )
            started = time.perf_counter()
            completion = await ai.language_model.complete(
                CompletionRequest(
                    messages=(
                        ChatMessage(
                            MessageRole.USER,
                            "Какая статья 152-ФЗ посвящена согласию субъекта на обработку его "
                            "персональных данных? Ответь кратко.",
                        ),
                    ),
                    response_schema=_PROBE_SCHEMA,
                    max_tokens=200,
                )
            )
            answer = json.loads(completion.text)
            typer.echo(
                f"language model {ai.language_model.model}: {time.perf_counter() - started:.2f}s, "
                f"structured answer keys={sorted(answer)}"
            )

    asyncio.run(run())
