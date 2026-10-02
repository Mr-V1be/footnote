from __future__ import annotations

from snoska.bootstrap.settings import StorageBackend, StorageSettings
from snoska.infrastructure.storage.filesystem import FileSystemBlobStorage
from snoska.infrastructure.storage.s3 import S3BlobStorage, S3Config
from snoska.ports.blob_storage import BlobStorage


def local_storage(settings: StorageSettings) -> FileSystemBlobStorage:
    return FileSystemBlobStorage(settings.blob_root)


def s3_storage(settings: StorageSettings) -> S3BlobStorage:
    return S3BlobStorage(
        S3Config(
            endpoint=settings.s3_endpoint,
            access_key=settings.s3_access_key.get_secret_value(),
            secret_key=settings.s3_secret_key.get_secret_value(),
            bucket=settings.s3_bucket,
            secure=settings.s3_secure,
            region=settings.s3_region,
        )
    )


def build_blob_storage(settings: StorageSettings) -> BlobStorage:
    """The configured store; the adapters are interchangeable behind the port."""
    if settings.storage_backend is StorageBackend.S3:
        return s3_storage(settings)
    return local_storage(settings)
