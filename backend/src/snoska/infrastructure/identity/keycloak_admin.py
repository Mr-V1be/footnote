from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from snoska.domain.tenancy.members import Member, MemberNotFoundError
from snoska.ports.identity import (
    IdentityProviderError,
    Invitation,
    MemberSpec,
    OrganizationProfile,
)

TOKEN_SAFETY_MARGIN_SECONDS = 30
PAGE_SIZE = 100
# Actions an invited user completes from the email: verify it, set a password.
INVITE_ACTIONS = ["VERIFY_EMAIL", "UPDATE_PASSWORD"]
INVITE_LIFESPAN_SECONDS = 7 * 24 * 3600


@dataclass(frozen=True, slots=True)
class KeycloakAdminConfig:
    base_url: str
    realm: str
    client_id: str
    client_secret: str
    api_client_id: str
    # Invitation emails link back to the web app through its client.
    web_client_id: str = "snoska-web"
    web_url: str = "http://localhost:46300"


class KeycloakAdminClient:
    """Keycloak Admin REST API through the directory service account.

    Implements the read side (organization profiles) and idempotent
    provisioning of organizations, role groups and members.
    """

    def __init__(self, http: httpx.AsyncClient, config: KeycloakAdminConfig) -> None:
        self._http = http
        self._config = config
        self._token: str | None = None
        self._token_expires = 0.0
        self._lock = asyncio.Lock()
        self._api_client_uuid: str | None = None

    @property
    def _admin(self) -> str:
        return f"{self._config.base_url}/admin/realms/{self._config.realm}"

    async def _access_token(self) -> str:
        async with self._lock:
            if self._token and time.monotonic() < self._token_expires:
                return self._token
            try:
                response = await self._http.post(
                    f"{self._config.base_url}/realms/{self._config.realm}/protocol/openid-connect/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._config.client_id,
                        "client_secret": self._config.client_secret,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise IdentityProviderError(f"cannot authenticate to Keycloak: {exc!r}") from exc
            body = response.json()
            self._token = str(body["access_token"])
            self._token_expires = (
                time.monotonic() + float(body.get("expires_in", 60)) - TOKEN_SAFETY_MARGIN_SECONDS
            )
            return self._token

    async def _call(
        self, method: str, path: str, *, ok: tuple[int, ...] = (200, 201, 204), **kwargs: Any
    ) -> httpx.Response:
        token = await self._access_token()
        headers = {**kwargs.pop("headers", {}), "Authorization": f"Bearer {token}"}
        try:
            response = await self._http.request(
                method, f"{self._admin}{path}", headers=headers, **kwargs
            )
        except httpx.HTTPError as exc:
            raise IdentityProviderError(f"Keycloak request failed: {exc!r}") from exc
        if response.status_code not in ok:
            raise IdentityProviderError(
                f"Keycloak {method} {path} answered {response.status_code}: {response.text[:300]}"
            )
        return response

    # ── Read side ────────────────────────────────────────────────────────────

    async def get_organization(self, organization_id: UUID) -> OrganizationProfile | None:
        response = await self._call("GET", f"/organizations/{organization_id}", ok=(200, 404))
        if response.status_code == 404:
            return None
        body = response.json()
        return OrganizationProfile(id=UUID(body["id"]), alias=body["alias"], name=body["name"])

    async def list_members(self, organization_id: UUID) -> list[Member]:
        roles: dict[str, set[str]] = {}
        users: dict[str, dict[str, Any]] = {}
        for role_code, group_id in (await self._groups(organization_id)).items():
            path = f"/organizations/{organization_id}/groups/{group_id}/members"
            for user in await self._all(path):
                users[user["id"]] = user
                roles.setdefault(user["id"], set()).add(role_code)
        for user in await self._all(f"/organizations/{organization_id}/members"):
            users.setdefault(user["id"], user)
        return [
            Member(
                user_id=UUID(user_id),
                email=user.get("email"),
                first_name=user.get("firstName") or "",
                last_name=user.get("lastName") or "",
                role_codes=frozenset(roles.get(user_id, set())),
                pending="UPDATE_PASSWORD" in (user.get("requiredActions") or []),
            )
            for user_id, user in users.items()
        ]

    async def _all(self, path: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        first = 0
        while True:
            page = (await self._call("GET", path, params={"first": first, "max": PAGE_SIZE})).json()
            found.extend(page)
            if len(page) < PAGE_SIZE:
                return found
            first += PAGE_SIZE

    async def realm_role_emails(self, role: str) -> list[str]:
        """Emails of the users holding a realm role (the platform's operators)."""
        users = (await self._call("GET", f"/roles/{role}/users", ok=(200, 404))).json()
        if not isinstance(users, list):
            return []
        return [str(user["email"]) for user in users if user.get("email")]

    # ── Member administration ────────────────────────────────────────────────

    async def invite(self, organization_id: UUID, invitation: Invitation) -> UUID:
        email = invitation.email.strip().lower()
        found = (
            await self._call("GET", "/users", params={"username": email, "exact": "true"})
        ).json()
        if found:
            user_id = str(found[0]["id"])
            fresh = False
        else:
            await self._call(
                "POST",
                "/users",
                json={
                    "username": email,
                    "email": email,
                    "firstName": invitation.first_name,
                    "lastName": invitation.last_name,
                    "enabled": True,
                    "emailVerified": False,
                    "requiredActions": INVITE_ACTIONS,
                },
            )
            created = (
                await self._call("GET", "/users", params={"username": email, "exact": "true"})
            ).json()
            user_id = str(created[0]["id"])
            fresh = True
        await self._call(
            "POST", f"/organizations/{organization_id}/members", json=user_id, ok=(201, 204, 409)
        )
        await self.set_role(organization_id, UUID(user_id), invitation.role_code)
        if fresh:
            await self._call(
                "PUT",
                f"/users/{user_id}/execute-actions-email",
                params={
                    "client_id": self._config.web_client_id,
                    "redirect_uri": self._config.web_url,
                    "lifespan": INVITE_LIFESPAN_SECONDS,
                },
                json=INVITE_ACTIONS,
            )
        return UUID(user_id)

    async def set_role(self, organization_id: UUID, user_id: UUID, role_code: str) -> None:
        groups = await self._groups(organization_id)
        if role_code not in groups:
            raise IdentityProviderError(f"organization has no group for role {role_code!r}")
        member = await self._call(
            "GET", f"/organizations/{organization_id}/members/{user_id}", ok=(200, 404)
        )
        if member.status_code == 404:
            raise MemberNotFoundError("not a member of the organization")
        current = {
            group["name"]
            for group in (
                await self._call(
                    "GET", f"/organizations/{organization_id}/members/{user_id}/groups"
                )
            ).json()
        }
        for name, group_id in groups.items():
            path = f"/organizations/{organization_id}/groups/{group_id}/members/{user_id}"
            if name == role_code and name not in current:
                await self._call("PUT", path)
            elif name != role_code and name in current:
                await self._call("DELETE", path)

    async def remove(self, organization_id: UUID, user_id: UUID) -> None:
        groups = await self._groups(organization_id)
        for group_id in groups.values():
            await self._call(
                "DELETE",
                f"/organizations/{organization_id}/groups/{group_id}/members/{user_id}",
                ok=(204, 404),
            )
        await self._call(
            "DELETE", f"/organizations/{organization_id}/members/{user_id}", ok=(204, 404)
        )

    # ── Provisioning ─────────────────────────────────────────────────────────

    async def _find_organization(self, alias: str) -> dict[str, Any] | None:
        first = 0
        while True:
            page = (
                await self._call("GET", "/organizations", params={"first": first, "max": PAGE_SIZE})
            ).json()
            for organization in page:
                if organization.get("alias") == alias:
                    return dict(organization)
            if len(page) < PAGE_SIZE:
                return None
            first += PAGE_SIZE

    async def ensure_organization(self, alias: str, name: str, domain: str) -> OrganizationProfile:
        existing = await self._find_organization(alias)
        if existing is None:
            await self._call(
                "POST",
                "/organizations",
                json={"name": name, "alias": alias, "enabled": True, "domains": [{"name": domain}]},
            )
            existing = await self._find_organization(alias)
            if existing is None:
                raise IdentityProviderError(f"organization {alias} was not created")
        elif existing.get("name") != name:
            await self._call(
                "PUT", f"/organizations/{existing['id']}", json={**existing, "name": name}
            )
        return OrganizationProfile(id=UUID(existing["id"]), alias=alias, name=name)

    async def _api_client(self) -> str:
        if self._api_client_uuid is None:
            clients = (
                await self._call("GET", "/clients", params={"clientId": self._config.api_client_id})
            ).json()
            if not clients:
                raise IdentityProviderError("API client is not registered in Keycloak")
            self._api_client_uuid = str(clients[0]["id"])
        return self._api_client_uuid

    async def _groups(self, organization_id: UUID) -> dict[str, str]:
        groups = (await self._call("GET", f"/organizations/{organization_id}/groups")).json()
        return {group["name"]: group["id"] for group in groups}

    async def ensure_role_groups(self, organization_id: UUID, role_codes: tuple[str, ...]) -> None:
        client_uuid = await self._api_client()
        groups = await self._groups(organization_id)
        for role_code in role_codes:
            if role_code not in groups:
                created = await self._call(
                    "POST", f"/organizations/{organization_id}/groups", json={"name": role_code}
                )
                groups[role_code] = created.json()["id"]
            group_path = f"/organizations/{organization_id}/groups/{groups[role_code]}"
            mapping = f"{group_path}/role-mappings/clients/{client_uuid}"
            assigned = {role["name"] for role in (await self._call("GET", mapping)).json()}
            if role_code not in assigned:
                role = (await self._call("GET", f"/clients/{client_uuid}/roles/{role_code}")).json()
                await self._call("POST", mapping, json=[role])

    async def _ensure_user(self, email: str, first_name: str, last_name: str, password: str) -> str:
        found = (
            await self._call("GET", "/users", params={"username": email, "exact": "true"})
        ).json()
        profile = {
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
        }
        if found:
            user_id = str(found[0]["id"])
            await self._call("PUT", f"/users/{user_id}", json=profile)
        else:
            await self._call("POST", "/users", json=profile)
            created = (
                await self._call("GET", "/users", params={"username": email, "exact": "true"})
            ).json()
            user_id = str(created[0]["id"])
        await self._call(
            "PUT",
            f"/users/{user_id}/reset-password",
            json={"type": "password", "value": password, "temporary": False},
        )
        return user_id

    async def ensure_member(self, organization_id: UUID, member: MemberSpec) -> UUID:
        user_id = await self._ensure_user(
            member.email, member.first_name, member.last_name, member.password
        )
        # The endpoint takes the bare user id as a JSON string.
        await self._call(
            "POST",
            f"/organizations/{organization_id}/members",
            json=user_id,
            ok=(201, 204, 409),
        )
        groups = await self._groups(organization_id)
        current = {
            group["name"]
            for group in (
                await self._call(
                    "GET", f"/organizations/{organization_id}/members/{user_id}/groups"
                )
            ).json()
        }
        for name, group_id in groups.items():
            path = f"/organizations/{organization_id}/groups/{group_id}/members/{user_id}"
            if name == member.role_code and name not in current:
                await self._call("PUT", path)
            elif name != member.role_code and name in current:
                await self._call("DELETE", path)
        return UUID(user_id)

    async def ensure_platform_user(
        self, email: str, first_name: str, last_name: str, password: str, realm_role: str
    ) -> UUID:
        user_id = await self._ensure_user(email, first_name, last_name, password)
        role = (await self._call("GET", f"/roles/{realm_role}")).json()
        await self._call("POST", f"/users/{user_id}/role-mappings/realm", json=[role])
        return UUID(user_id)
