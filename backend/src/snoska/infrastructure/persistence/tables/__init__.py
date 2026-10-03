"""Table definitions. Importing this package registers every table."""

from snoska.infrastructure.persistence.tables import (
    ask,
    audit,
    autofix,
    billing,
    checks,
    corpus,
    documents,
    integrations,
    operations,
    outbox,
    tenancy,
)
from snoska.infrastructure.persistence.tables.metadata import metadata

__all__ = [
    "ask",
    "audit",
    "autofix",
    "billing",
    "checks",
    "corpus",
    "documents",
    "integrations",
    "metadata",
    "operations",
    "outbox",
    "tenancy",
]
