from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from footnote.domain.tenancy.access import MembershipClaim, Principal
from footnote.ports.identity import AuthenticationError


def _roles(container: Any, client_id: str) -> frozenset[str]:
    if not isinstance(container, Mapping):
        return frozenset()
    client = container.get(client_id)
    roles = client.get("roles") if isinstance(client, Mapping) else None
    return frozenset(str(role) for role in roles) if isinstance(roles, list) else frozenset()


class KeycloakClaimsMapper:
    """Reads Keycloak's token layout.

    Organization membership comes from the ``organization`` claim, where each
    organization alias maps to its id and the client roles granted through the
    organization's groups::

        "organization": {
            "acme": {"id": "…", "resource_access": {"footnote-api": {"roles": ["lawyer"]}}}
        }
    """

    def __init__(self, api_client_id: str) -> None:
        self._api_client_id = api_client_id

    def principal(self, claims: Mapping[str, Any]) -> Principal:
        try:
            user_id = UUID(str(claims["sub"]))
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("token has no valid subject") from exc
        name = claims.get("name") or claims.get("preferred_username") or claims.get("email") or ""
        realm_access = claims.get("realm_access")
        realm_roles = realm_access.get("roles", []) if isinstance(realm_access, Mapping) else []
        return Principal(
            user_id=user_id,
            email=claims.get("email"),
            display_name=str(name),
            memberships=self._memberships(claims.get("organization")),
            platform_role_codes=frozenset(str(role) for role in realm_roles),
        )

    def _memberships(self, claim: Any) -> tuple[MembershipClaim, ...]:
        if not isinstance(claim, Mapping):
            return ()
        memberships: list[MembershipClaim] = []
        for alias, details in claim.items():
            if not isinstance(details, Mapping) or "id" not in details:
                continue
            try:
                organization_id = UUID(str(details["id"]))
            except ValueError:
                continue
            memberships.append(
                MembershipClaim(
                    organization_id=organization_id,
                    organization_alias=str(alias),
                    role_codes=_roles(details.get("resource_access"), self._api_client_id),
                )
            )
        return tuple(sorted(memberships, key=lambda m: m.organization_alias))
