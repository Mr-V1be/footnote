from __future__ import annotations

import asyncio
import math
import time
from typing import Any

import httpx
import jwt

from snoska.ports.identity import AuthenticationError, IdentityProviderError

DEFAULT_TTL_SECONDS = 600
MIN_REFRESH_INTERVAL_SECONDS = 30


class JwksKeySource:
    """Signing keys of the identity provider, cached by key id.

    An unknown key id triggers a refresh (keys rotate), rate-limited so a
    flood of forged tokens cannot hammer the provider.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        jwks_url: str,
        *,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        min_refresh_interval: float = MIN_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        self._client = client
        self._jwks_url = jwks_url
        self._ttl = ttl_seconds
        self._min_interval = min_refresh_interval
        self._keys: dict[str, jwt.PyJWK] = {}
        # Monotonic time starts near zero after boot, so "never fetched" must
        # not be encoded as 0.0: that would rate-limit the very first fetch.
        self._fetched_at: float | None = None
        self._lock = asyncio.Lock()

    async def key(self, kid: str) -> jwt.PyJWK:
        if kid in self._keys and self._age() < self._ttl:
            return self._keys[kid]
        async with self._lock:
            age = self._age()
            stale = age >= self._ttl
            missing = kid not in self._keys
            if (stale or missing) and age >= self._min_interval:
                await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise AuthenticationError("token is signed with an unknown key")
        return key

    def _age(self) -> float:
        if self._fetched_at is None:
            return math.inf
        return time.monotonic() - self._fetched_at

    async def _refresh(self) -> None:
        try:
            response = await self._client.get(self._jwks_url)
            response.raise_for_status()
            document: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IdentityProviderError(f"cannot load signing keys: {exc!r}") from exc
        keys: dict[str, jwt.PyJWK] = {}
        for entry in document.get("keys", []):
            if entry.get("use", "sig") != "sig" or "kid" not in entry:
                continue
            try:
                keys[entry["kid"]] = jwt.PyJWK(entry)
            except jwt.PyJWKError:
                continue
        self._keys = keys
        self._fetched_at = time.monotonic()
