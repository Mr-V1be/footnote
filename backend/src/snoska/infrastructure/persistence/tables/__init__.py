"""Table definitions. Importing this package registers every table."""

from snoska.infrastructure.persistence.tables import corpus, documents, outbox, tenancy
from snoska.infrastructure.persistence.tables.metadata import metadata

__all__ = ["corpus", "documents", "metadata", "outbox", "tenancy"]
