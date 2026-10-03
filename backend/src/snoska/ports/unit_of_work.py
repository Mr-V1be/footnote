from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from snoska.domain.shared.errors import ConflictError
from snoska.ports.audit.log import AuditLog
from snoska.ports.billing.repositories import (
    InvoiceRepository,
    LedgerRepository,
    PaymentEventLog,
    SubscriptionRepository,
)
from snoska.ports.checks.embeddings import EmbeddingCache
from snoska.ports.checks.repositories import (
    CheckResultRepository,
    CheckRunRepository,
    FindingRepository,
)
from snoska.ports.corpus_repositories import CorpusRepository
from snoska.ports.document_repositories import (
    DocumentRepository,
    DocumentStructureRepository,
    DocumentVersionRepository,
)
from snoska.ports.integrations.repositories import (
    ApiKeyRepository,
    WebhookDeliveryRepository,
    WebhookEndpointRepository,
)
from snoska.ports.outbox import OutboxRepository
from snoska.ports.tenancy_repositories import (
    OrganizationRepository,
    UserProfileRepository,
    WorkspaceMemberRepository,
    WorkspaceRepository,
)


class ConcurrentModificationError(ConflictError):
    code = "concurrent_modification"


class UnitOfWork(Protocol):
    """One database transaction.

    Opened either for a tenant (tenant tables are visible only for that
    organization, enforced by the database) or for the platform (tenant
    tables are invisible). Leaving the context without ``commit`` rolls back.
    """

    @property
    def organizations(self) -> OrganizationRepository: ...

    @property
    def workspaces(self) -> WorkspaceRepository: ...

    @property
    def profiles(self) -> UserProfileRepository: ...

    @property
    def documents(self) -> DocumentRepository: ...

    @property
    def versions(self) -> DocumentVersionRepository: ...

    @property
    def structures(self) -> DocumentStructureRepository: ...

    @property
    def corpus(self) -> CorpusRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    @property
    def check_runs(self) -> CheckRunRepository: ...

    @property
    def check_results(self) -> CheckResultRepository: ...

    @property
    def findings(self) -> FindingRepository: ...

    @property
    def workspace_members(self) -> WorkspaceMemberRepository: ...

    @property
    def audit(self) -> AuditLog: ...

    @property
    def api_keys(self) -> ApiKeyRepository: ...

    @property
    def webhook_endpoints(self) -> WebhookEndpointRepository: ...

    @property
    def webhook_deliveries(self) -> WebhookDeliveryRepository: ...

    @property
    def subscriptions(self) -> SubscriptionRepository: ...

    @property
    def ledger(self) -> LedgerRepository: ...

    @property
    def invoices(self) -> InvoiceRepository: ...

    @property
    def payment_events(self) -> PaymentEventLog: ...

    @property
    def embeddings(self) -> EmbeddingCache:
        """Vectors of the tenant's passages; only in a tenant unit of work."""
        ...

    async def commit(self) -> None: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class UnitOfWorkFactory(Protocol):
    def for_tenant(self, organization_id: UUID) -> UnitOfWork: ...

    def for_platform(self) -> UnitOfWork: ...
