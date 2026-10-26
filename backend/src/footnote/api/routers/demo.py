from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Request, Response, status

from footnote.api.dependencies import ContainerDep, OrganizationAlias

router = APIRouter(prefix="/v1/demo", tags=["demo"], include_in_schema=False)


@router.post("/webhooks/{organization}/{endpoint_id}")
async def demo_webhook_receiver(
    request: Request,
    container: ContainerDep,
    organization: OrganizationAlias,
    endpoint_id: UUID,
    signature: str = Header(default="", alias="Footnote-Signature"),
) -> Response:
    """A receiver for the demo stand's webhooks: accepts what is signed with
    the endpoint's secret, like an integration would. Mounted on demo stands only."""
    tenant = await container.tenant_access.organization_by_alias(organization)
    body = await request.body()
    accepted = await container.webhooks.accept_demo_delivery(
        tenant.id, endpoint_id, signature, body
    )
    return Response(
        status_code=status.HTTP_204_NO_CONTENT if accepted else status.HTTP_401_UNAUTHORIZED
    )
