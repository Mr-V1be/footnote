from __future__ import annotations

import hashlib
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path

import anyio

from snoska.ports.blob_storage import BlobTooLargeError, StoredBlob

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$")


class FileSystemBlobStorage:
    """Blob storage on a local or mounted volume.

    Writes go to a temporary file in the target directory and are renamed
    into place, so a reader never sees a partially written blob.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key) or ".." in key.split("/"):
            raise ValueError(f"invalid blob key {key!r}")
        path = (self._root / key).resolve()
        if self._root not in path.parents:
            raise ValueError(f"blob key escapes the storage root: {key!r}")
        return path

    async def put(self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int) -> StoredBlob:
        path = self._path(key)
        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.part")
        digest = hashlib.sha256()
        size = 0
        try:
            async with await anyio.open_file(temporary, "wb") as handle:
                async for chunk in chunks:
                    size += len(chunk)
                    if size > max_bytes:
                        raise BlobTooLargeError(f"file exceeds {max_bytes} bytes")
                    digest.update(chunk)
                    await handle.write(chunk)
            await anyio.Path(temporary).rename(path)
        except BaseException:
            await anyio.Path(temporary).unlink(missing_ok=True)
            raise
        return StoredBlob(key=key, size_bytes=size, sha256=digest.hexdigest())

    async def read(self, key: str) -> bytes:
        return await anyio.Path(self._path(key)).read_bytes()

    async def stream(self, key: str, *, chunk_size: int) -> AsyncIterator[bytes]:
        async with await anyio.open_file(self._path(key), "rb") as handle:
            while chunk := await handle.read(chunk_size):
                yield chunk

    async def delete(self, key: str) -> None:
        await anyio.Path(self._path(key)).unlink(missing_ok=True)
