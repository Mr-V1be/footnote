from __future__ import annotations

from typing import Annotated, cast

import structlog
from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from snoska.bootstrap.container import Container
from snoska.domain.tenancy.access import OrganizationAccess, PlatformAccess, Principal
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.identity import AuthenticationError

_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_principal(
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("bearer token required")
    principal = await container.verifier.verify(credentials.credentials)
    structlog.contextvars.bind_contextvars(user_id=str(principal.user_id))
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]

OrganizationAlias = Annotated[str, Path(min_length=1, max_length=63, pattern=r"^[a-z0-9-]+$")]


async def get_organization_access(
    container: ContainerDep, principal: PrincipalDep, organization: OrganizationAlias
) -> OrganizationAccess:
    access = await container.tenant_access.organization_access(principal, organization)
    structlog.contextvars.bind_contextvars(organization_id=str(access.organization_id))
    return access


OrganizationAccessDep = Annotated[OrganizationAccess, Depends(get_organization_access)]


def get_platform_access(container: ContainerDep, principal: PrincipalDep) -> PlatformAccess:
    return container.tenant_access.platform_access(principal)


PlatformAccessDep = Annotated[PlatformAccess, Depends(get_platform_access)]


def require_corpus_reader(container: ContainerDep, principal: PrincipalDep) -> Principal:
    container.tenant_access.require_anywhere(principal, Permission.CORPUS_READ)
    return principal


CorpusReaderDep = Annotated[Principal, Depends(require_corpus_reader)]
