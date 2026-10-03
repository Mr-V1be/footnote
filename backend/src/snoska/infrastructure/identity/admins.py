from __future__ import annotations

from collections.abc import Sequence

from snoska.infrastructure.identity.keycloak_admin import KeycloakAdminClient


class KeycloakPlatformAdmins:
    """The platform's operators: holders of a realm role in Keycloak."""

    def __init__(self, keycloak: KeycloakAdminClient, role: str) -> None:
        self._keycloak = keycloak
        self._role = role

    async def emails(self) -> Sequence[str]:
        return await self._keycloak.realm_role_emails(self._role)
