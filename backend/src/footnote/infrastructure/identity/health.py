from __future__ import annotations

import httpx
import structlog

log = structlog.get_logger(__name__)


class IdentityHealth:
    """The identity provider publishes the realm's configuration."""

    name = "identity"

    def __init__(self, http: httpx.AsyncClient, issuer: str) -> None:
        self._http = http
        self._url = f"{issuer}/.well-known/openid-configuration"

    async def check(self) -> bool:
        try:
            response = await self._http.get(self._url, timeout=3)
        except httpx.HTTPError as exc:
            log.warning("health.identity_unavailable", error=repr(exc))
            return False
        return response.status_code == httpx.codes.OK
