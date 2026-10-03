from __future__ import annotations

from sqlalchemy import MetaData

# Deterministic constraint names keep migrations reviewable and reversible.
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

# Name of the transaction-local setting that carries the current tenant.
# Row-level security policies compare tenant columns against it.
TENANT_SETTING = "snoska.tenant_id"

# Tables whose rows belong to exactly one organization and are protected by
# row-level security. Kept here so migrations and tests share one list.
TENANT_TABLES: tuple[str, ...] = (
    "workspaces",
    "documents",
    "document_versions",
    "document_structures",
    "document_blocks",
    "check_runs",
    "check_results",
    "findings",
    "text_embeddings",
    "workspace_members",
    "audit_events",
    "api_keys",
    "webhook_endpoints",
    "webhook_deliveries",
)
