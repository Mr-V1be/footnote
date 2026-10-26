from __future__ import annotations

from footnote.ports.blob_storage import BlobStorage


class StorageHealth:
    """Readiness of the blob store (the bucket or the directory)."""

    name = "storage"

    def __init__(self, storage: BlobStorage) -> None:
        self._storage = storage

    async def check(self) -> bool:
        return await self._storage.available()
