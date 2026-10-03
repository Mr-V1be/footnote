from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from snoska.api.dependencies import ContainerDep, OrganizationAccessDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.schemas.admin.integrations import (
    ApiKeyIn,
    ApiKeyOut,
    DeliveryOut,
    IssuedKeyOut,
    WebhookIn,
    WebhookOut,
    WebhookWithSecretOut,
)
from snoska.application.integrations.webhooks import EndpointSpec

router = APIRouter(
    prefix="/v1/organizations/{organization}", tags=["integrations"], responses=PROBLEM_RESPONSES
)


@router.get("/api-keys", response_model=list[ApiKeyOut], response_model_by_alias=True)
async def list_api_keys(container: ContainerDep, access: OrganizationAccessDep) -> list[ApiKeyOut]:
    return [ApiKeyOut.of(key) for key in await container.api_keys.list(access)]


@router.post(
    "/api-keys",
    response_model=IssuedKeyOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    container: ContainerDep, access: OrganizationAccessDep, body: ApiKeyIn
) -> IssuedKeyOut:
    """A new key; its token is in this response and nowhere else."""
    issued = await container.api_keys.create(access, name=body.name, scopes=frozenset(body.scopes))
    return IssuedKeyOut(key=ApiKeyOut.of(issued.key), token=issued.token)


@router.delete("/api-keys/{key_id}", response_model=ApiKeyOut, response_model_by_alias=True)
async def revoke_api_key(
    container: ContainerDep, access: OrganizationAccessDep, key_id: UUID
) -> ApiKeyOut:
    return ApiKeyOut.of(await container.api_keys.revoke(access, key_id))


def _spec(body: WebhookIn) -> EndpointSpec:
    return EndpointSpec(
        url=body.url,
        description=body.description,
        events=frozenset(body.events),
        active=body.active,
    )


@router.get("/webhooks", response_model=list[WebhookOut], response_model_by_alias=True)
async def list_webhooks(container: ContainerDep, access: OrganizationAccessDep) -> list[WebhookOut]:
    return [WebhookOut.of(endpoint) for endpoint in await container.webhooks.list(access)]


@router.post(
    "/webhooks",
    response_model=WebhookWithSecretOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    container: ContainerDep, access: OrganizationAccessDep, body: WebhookIn
) -> WebhookWithSecretOut:
    endpoint = await container.webhooks.create(access, _spec(body))
    return WebhookWithSecretOut(endpoint=WebhookOut.of(endpoint), secret=endpoint.secret)


@router.put("/webhooks/{endpoint_id}", response_model=WebhookOut, response_model_by_alias=True)
async def update_webhook(
    container: ContainerDep, access: OrganizationAccessDep, endpoint_id: UUID, body: WebhookIn
) -> WebhookOut:
    return WebhookOut.of(await container.webhooks.update(access, endpoint_id, _spec(body)))


@router.post(
    "/webhooks/{endpoint_id}/secret",
    response_model=WebhookWithSecretOut,
    response_model_by_alias=True,
)
async def rotate_webhook_secret(
    container: ContainerDep, access: OrganizationAccessDep, endpoint_id: UUID
) -> WebhookWithSecretOut:
    endpoint = await container.webhooks.rotate_secret(access, endpoint_id)
    return WebhookWithSecretOut(endpoint=WebhookOut.of(endpoint), secret=endpoint.secret)


@router.delete("/webhooks/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    container: ContainerDep, access: OrganizationAccessDep, endpoint_id: UUID
) -> None:
    await container.webhooks.delete(access, endpoint_id)


@router.get(
    "/webhooks/{endpoint_id}/deliveries",
    response_model=list[DeliveryOut],
    response_model_by_alias=True,
)
async def webhook_deliveries(
    container: ContainerDep, access: OrganizationAccessDep, endpoint_id: UUID
) -> list[DeliveryOut]:
    """The latest deliveries to the endpoint, newest first."""
    return [
        DeliveryOut.of(item) for item in await container.webhooks.deliveries(access, endpoint_id)
    ]


@router.post(
    "/webhooks/{endpoint_id}/ping",
    response_model=DeliveryOut,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ping_webhook(
    container: ContainerDep, access: OrganizationAccessDep, endpoint_id: UUID
) -> DeliveryOut:
    return DeliveryOut.of(await container.webhooks.ping(access, endpoint_id))


@router.post(
    "/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry",
    response_model=DeliveryOut,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_delivery(
    container: ContainerDep, access: OrganizationAccessDep, endpoint_id: UUID, delivery_id: UUID
) -> DeliveryOut:
    return DeliveryOut.of(await container.webhooks.redeliver(access, endpoint_id, delivery_id))
