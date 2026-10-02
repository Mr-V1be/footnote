from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncIterator
from pathlib import Path

import anyio

from snoska.infrastructure.storage.keys import validate_key
from snoska.ports.blob_storage import BlobNotFoundError, BlobTooLargeError, StoredBlob


class FileSystemBlobStorage:
    """Blob storage on a local or mounted volume.

    Writes go to a temporary file in the target directory and are renamed
    into place, so a reader never sees a partially written blob.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / validate_key(key)).resolve()
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
        try:
            return await anyio.Path(self._path(key)).read_bytes()
        except FileNotFoundError as exc:
            raise BlobNotFoundError(f"no blob {key!r}") from exc

    async def stream(self, key: str, *, chunk_size: int) -> AsyncIterator[bytes]:
        try:
            handle = await anyio.open_file(self._path(key), "rb")
        except FileNotFoundError as exc:
            raise BlobNotFoundError(f"no blob {key!r}") from exc
        async with handle:
            while chunk := await handle.read(chunk_size):
                yield chunk

    async def delete(self, key: str) -> None:
        await anyio.Path(self._path(key)).unlink(missing_ok=True)

    async def exists(self, key: str) -> bool:
        return await anyio.Path(self._path(key)).is_file()

    async def keys(self) -> AsyncIterator[str]:
        """Every stored key, for copying the store elsewhere."""
        root = anyio.Path(self._root)
        if not await root.is_dir():
            return
        async for path in root.rglob("*"):
            if await path.is_file() and not path.name.startswith("."):
                yield str(Path(path).relative_to(self._root))

    async def available(self) -> bool:
        try:
            await anyio.Path(self._root).mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return os.access(self._root, os.W_OK)
