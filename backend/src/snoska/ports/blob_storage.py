from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from snoska.domain.shared.errors import TooLargeError


class BlobTooLargeError(TooLargeError):
    code = "file_too_large"


@dataclass(frozen=True, slots=True)
class StoredBlob:
    key: str
    size_bytes: int
    sha256: str


class BlobStorage(Protocol):
    """Content-addressed-by-caller object storage for original uploads."""

    async def put(self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int) -> StoredBlob:
        """Store a stream under ``key``; raise BlobTooLargeError past ``max_bytes``."""
        ...

    async def read(self, key: str) -> bytes: ...

    def stream(self, key: str, *, chunk_size: int) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...
