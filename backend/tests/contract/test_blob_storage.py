"""Both blob stores keep the same contract: what is put is read back whole."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from minio import Minio

from footnote.infrastructure.storage.filesystem import FileSystemBlobStorage
from footnote.infrastructure.storage.s3 import S3BlobStorage, S3Config
from footnote.ports.blob_storage import BlobNotFoundError, BlobStorage, BlobTooLargeError

S3_ENDPOINT = os.environ.get("FOOTNOTE_TEST_S3_ENDPOINT")


async def chunks(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        yield part


@pytest.fixture(params=["local", "s3"])
def storage(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[BlobStorage]:
    if request.param == "local":
        yield FileSystemBlobStorage(tmp_path)
        return
    if not S3_ENDPOINT:
        pytest.skip("no S3 endpoint for tests (FOOTNOTE_TEST_S3_ENDPOINT)")
    access, secret = (
        os.environ["FOOTNOTE_TEST_S3_ACCESS_KEY"],
        os.environ["FOOTNOTE_TEST_S3_SECRET_KEY"],
    )
    bucket = f"test-{uuid4().hex[:12]}"
    yield S3BlobStorage(
        S3Config(endpoint=S3_ENDPOINT, access_key=access, secret_key=secret, bucket=bucket)
    )
    # Leave the shared store as it was.
    client = Minio(S3_ENDPOINT, access_key=access, secret_key=secret, secure=False)
    if client.bucket_exists(bucket):
        for item in client.list_objects(bucket, recursive=True):
            client.remove_object(bucket, item.object_name or "")
        client.remove_bucket(bucket)


async def test_a_stored_blob_reads_back_streams_and_goes_away(storage: BlobStorage) -> None:
    key = f"org/{uuid4()}/original.docx"
    assert not await storage.exists(key)
    stored = await storage.put(key, chunks(b"PK\x03\x04", b"document"), max_bytes=1024)
    assert stored.size_bytes == 12
    assert await storage.exists(key)
    assert await storage.read(key) == b"PK\x03\x04document"
    assert b"".join([part async for part in storage.stream(key, chunk_size=5)]) == (
        b"PK\x03\x04document"
    )
    await storage.delete(key)
    with pytest.raises(BlobNotFoundError):
        await storage.read(key)
    assert await storage.available()


async def test_an_oversized_upload_leaves_nothing_behind(storage: BlobStorage) -> None:
    key = f"org/{uuid4()}/big.pdf"
    with pytest.raises(BlobTooLargeError):
        await storage.put(key, chunks(b"x" * 600, b"x" * 600), max_bytes=1000)
    assert not await storage.exists(key)


async def test_keys_cannot_escape_the_store(storage: BlobStorage) -> None:
    with pytest.raises(ValueError, match="invalid blob key"):
        await storage.read("../etc/passwd")


async def test_keys_are_listed_under_a_prefix(storage: BlobStorage) -> None:
    tenant = f"tenants/{uuid4()}"
    for name in ("a/original.docx", "b/original.pdf"):
        await storage.put(f"{tenant}/{name}", chunks(b"data"), max_bytes=1024)
    await storage.put(f"tenants/{uuid4()}/c/original.docx", chunks(b"other"), max_bytes=1024)
    listed = sorted([key async for key in storage.keys(f"{tenant}/")])
    assert listed == [f"{tenant}/a/original.docx", f"{tenant}/b/original.pdf"]
