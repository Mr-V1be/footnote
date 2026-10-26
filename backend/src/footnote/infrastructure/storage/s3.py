from __future__ import annotations

import hashlib
import tempfile
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, BinaryIO, cast

import anyio
import anyio.to_thread
from minio import Minio
from minio.error import S3Error

from footnote.infrastructure.storage.keys import validate_key
from footnote.ports.blob_storage import BlobNotFoundError, BlobTooLargeError, StoredBlob

# Uploads up to this size are buffered in memory, larger ones on disk.
SPOOL_IN_MEMORY_BYTES = 8 * 1024 * 1024
MISSING_CODES = frozenset({"NoSuchKey", "NoSuchObject", "NoSuchBucket"})


class ObjectStoreError(Exception):
    """An S3 call failed. Carries the S3 error code (the SDK's own exception
    type cannot cross the thread boundary: it refuses traceback updates)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _guarded[T](call: Callable[..., T], *args: Any) -> T:
    try:
        return call(*args)
    except S3Error as exc:
        raise ObjectStoreError(exc.code or "S3Error", exc.message or "") from None


@dataclass(frozen=True, slots=True)
class S3Config:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False
    region: str | None = None


class S3BlobStorage:
    """Blob storage in an S3-compatible object store (MinIO in the stand).

    The SDK is synchronous; its calls run in worker threads. An upload is
    spooled first, so its size limit and checksum are enforced before the
    object exists, and the object store only ever sees complete objects.
    """

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
            region=config.region,
        )
        self._bucket_ready = False
        self._bucket_lock = anyio.Lock()

    async def _run[T](self, call: Callable[..., T], *args: Any) -> T:
        return await anyio.to_thread.run_sync(_guarded, call, *args)

    async def ensure_bucket(self) -> None:
        async with self._bucket_lock:
            if self._bucket_ready:
                return
            bucket = self._config.bucket
            if not await self._run(self._client.bucket_exists, bucket):
                await self._run(self._client.make_bucket, bucket)
            self._bucket_ready = True

    async def available(self) -> bool:
        try:
            await self.ensure_bucket()
        except Exception:  # any failure means "not available"
            return False
        return True

    async def put(self, key: str, chunks: AsyncIterator[bytes], *, max_bytes: int) -> StoredBlob:
        validate_key(key)
        await self.ensure_bucket()
        digest = hashlib.sha256()
        size = 0
        with tempfile.SpooledTemporaryFile(max_size=SPOOL_IN_MEMORY_BYTES) as spool:
            async for chunk in chunks:
                size += len(chunk)
                if size > max_bytes:
                    raise BlobTooLargeError(f"file exceeds {max_bytes} bytes")
                digest.update(chunk)
                spool.write(chunk)
            spool.seek(0)
            await self._run(self._upload, key, cast(BinaryIO, spool), size)
        return StoredBlob(key=key, size_bytes=size, sha256=digest.hexdigest())

    def _upload(self, key: str, data: BinaryIO, size: int) -> None:
        self._client.put_object(self._config.bucket, key, data, size)

    async def read(self, key: str) -> bytes:
        validate_key(key)
        try:
            return await self._run(self._read, key)
        except ObjectStoreError as exc:
            if exc.code in MISSING_CODES:
                raise BlobNotFoundError(f"no blob {key!r}") from exc
            raise

    def _read(self, key: str) -> bytes:
        response = self._client.get_object(self._config.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def stream(self, key: str, *, chunk_size: int) -> AsyncIterator[bytes]:
        validate_key(key)
        try:
            response = await self._run(self._client.get_object, self._config.bucket, key)
        except ObjectStoreError as exc:
            if exc.code in MISSING_CODES:
                raise BlobNotFoundError(f"no blob {key!r}") from exc
            raise
        try:
            while chunk := await anyio.to_thread.run_sync(response.read, chunk_size):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    async def keys(self, prefix: str = "") -> AsyncIterator[str]:
        """Stored keys under a prefix, listed in a worker thread."""
        await self.ensure_bucket()
        names = await self._run(self._list, prefix)
        for name in names:
            yield name

    def _list(self, prefix: str) -> list[str]:
        objects = self._client.list_objects(self._config.bucket, prefix=prefix, recursive=True)
        return [item.object_name for item in objects if item.object_name]

    async def delete(self, key: str) -> None:
        validate_key(key)
        await self._run(self._client.remove_object, self._config.bucket, key)

    async def exists(self, key: str) -> bool:
        validate_key(key)
        try:
            await self._run(self._client.stat_object, self._config.bucket, key)
        except ObjectStoreError as exc:
            if exc.code in MISSING_CODES:
                return False
            raise
        return True
