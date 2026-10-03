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
    "outbox",
    "tenancy",
]
