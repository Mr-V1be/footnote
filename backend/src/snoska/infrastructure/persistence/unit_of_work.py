from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from snoska.infrastructure.persistence.repositories.audit import SqlAuditLog
from snoska.infrastructure.persistence.repositories.checks import (
    SqlCheckResultRepository,
    SqlCheckRunRepository,
    SqlFindingRepository,
)
from snoska.infrastructure.persistence.repositories.corpus import SqlCorpusRepository
from snoska.infrastructure.persistence.repositories.documents import (
    SqlDocumentRepository,
    SqlDocumentVersionRepository,
)
from snoska.infrastructure.persistence.repositories.embeddings import SqlTextEmbeddingRepository
from snoska.infrastructure.persistence.repositories.outbox import SqlOutboxRepository
from snoska.infrastructure.persistence.repositories.structures import (
    SqlDocumentStructureRepository,
)
from snoska.infrastructure.persistence.repositories.tenancy import (
    SqlOrganizationRepository,
    SqlUserProfileRepository,
    SqlWorkspaceMemberRepository,
    SqlWorkspaceRepository,
)
from snoska.infrastructure.persistence.tables.metadata import TENANT_SETTING


class SqlUnitOfWork:
    """A transaction on one pooled connection.

    The tenant is applied with a transaction-local setting before any
    statement runs, so row-level security scopes every query of the
    transaction and the setting can never leak to the next borrower of the
    connection.
    """

    organizations: SqlOrganizationRepository
    workspaces: SqlWorkspaceRepository
    profiles: SqlUserProfileRepository
    documents: SqlDocumentRepository
    versions: SqlDocumentVersionRepository
    structures: SqlDocumentStructureRepository
    corpus: SqlCorpusRepository
    outbox: SqlOutboxRepository
    check_runs: SqlCheckRunRepository
    check_results: SqlCheckResultRepository
    findings: SqlFindingRepository
    embeddings: SqlTextEmbeddingRepository
    workspace_members: SqlWorkspaceMemberRepository
    audit: SqlAuditLog

    def __init__(self, engine: AsyncEngine, tenant_id: UUID | None) -> None:
        self._engine = engine
        self._tenant_id = tenant_id
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None
        self._committed = False

    async def __aenter__(self) -> Self:
        connection = await self._engine.connect()
        self._connection = connection
        self._transaction = await connection.begin()
        tenant = str(self._tenant_id) if self._tenant_id is not None else ""
        await connection.execute(select(func.set_config(TENANT_SETTING, tenant, True)))
        self.organizations = SqlOrganizationRepository(connection)
        self.workspaces = SqlWorkspaceRepository(connection)
        self.profiles = SqlUserProfileRepository(connection)
        self.documents = SqlDocumentRepository(connection)
        self.versions = SqlDocumentVersionRepository(connection)
        self.structures = SqlDocumentStructureRepository(connection)
        self.corpus = SqlCorpusRepository(connection)
        self.outbox = SqlOutboxRepository(connection)
        self.check_runs = SqlCheckRunRepository(connection)
        self.check_results = SqlCheckResultRepository(connection)
        self.findings = SqlFindingRepository(connection)
        self.embeddings = SqlTextEmbeddingRepository(connection, self._tenant_id)
        self.workspace_members = SqlWorkspaceMemberRepository(connection, self._tenant_id)
        self.audit = SqlAuditLog(connection)
        return self

    async def commit(self) -> None:
        if self._transaction is None:
            raise RuntimeError("unit of work is not active")
        await self._transaction.commit()
        self._committed = True

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if self._transaction is not None and not self._committed:
                await self._transaction.rollback()
        finally:
            if self._connection is not None:
                await self._connection.close()
            self._connection = None
            self._transaction = None


class SqlUnitOfWorkFactory:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def for_tenant(self, organization_id: UUID) -> SqlUnitOfWork:
        return SqlUnitOfWork(self._engine, organization_id)

    def for_platform(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self._engine, None)
