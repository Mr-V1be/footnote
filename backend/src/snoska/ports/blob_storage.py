from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from snoska.domain.shared.errors import NotFoundError, TooLargeError


class BlobTooLargeError(TooLargeError):
    code = "file_too_large"


class BlobNotFoundError(NotFoundError):
    code = "file_missing"


@dataclass(frozen=True, slots=True)
class StoredBlob:
    key: str
    size_bytes: int
    sha256: str


class BlobStorage(Protocol):
    """Object storage for original uploads and generated files, keyed by the
    caller. Adapters: a local directory and an S3-compatible store."""

    async def put(self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int) -> StoredBlob:
        """Store a stream under ``key``; raise BlobTooLargeError past ``max_bytes``."""
        ...

    async def read(self, key: str) -> bytes: ...

    def stream(self, key: str, *, chunk_size: int) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    async def available(self) -> bool:
        """The store answers and accepts writes; never raises."""
        ...
