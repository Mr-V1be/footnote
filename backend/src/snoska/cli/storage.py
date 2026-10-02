from __future__ import annotations

import asyncio

import typer

from snoska.bootstrap.storage import local_storage, s3_storage
from snoska.cli.support import settings_for_cli

app = typer.Typer(help="File storage.", no_args_is_help=True)

COPY_CHUNK_BYTES = 1024 * 1024


@app.command("copy-to-s3")
def copy_to_s3() -> None:
    """Copy every file of the local store into the S3 bucket (idempotent).

    Used when a stand moves from the local directory to the object store:
    run it, then set SNOSKA_STORAGE_BACKEND=s3.
    """
    settings = settings_for_cli().storage

    async def run() -> tuple[int, int]:
        source, target = local_storage(settings), s3_storage(settings)
        copied = skipped = 0
        async for key in source.keys():
            if await target.exists(key):
                skipped += 1
                continue
            await target.put(key, source.stream(key, chunk_size=COPY_CHUNK_BYTES), max_bytes=2**40)
            copied += 1
        return copied, skipped

    copied, skipped = asyncio.run(run())
    typer.echo(f"copied {copied} files, {skipped} already in the bucket")
