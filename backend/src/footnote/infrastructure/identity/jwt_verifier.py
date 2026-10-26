from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import jwt

from footnote.domain.tenancy.access import Principal
from footnote.infrastructure.identity.claims import KeycloakClaimsMapper
from footnote.ports.identity import AuthenticationError


class KeySource(Protocol):
    async def key(self, kid: str) -> jwt.PyJWK: ...


@dataclass(frozen=True, slots=True)
class TokenPolicy:
    issuer: str
    audience: str
    leeway_seconds: int = 30
    algorithms: Sequence[str] = field(default=("RS256",))


class JwtTokenVerifier:
    """Verifies access tokens locally: signature, issuer, audience, lifetime."""

    def __init__(self, keys: KeySource, policy: TokenPolicy, claims: KeycloakClaimsMapper) -> None:
        self._keys = keys
        self._policy = policy
        self._claims = claims

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("malformed token") from exc
        kid = header.get("kid")
        if header.get("alg") not in self._policy.algorithms or not isinstance(kid, str):
            raise AuthenticationError("unsupported token signature")
        key = await self._keys.key(kid)
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=list(self._policy.algorithms),
                audience=self._policy.audience,
                issuer=self._policy.issuer,
                leeway=self._policy.leeway_seconds,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("token expired") from exc
        except jwt.PyJWTError as exc:
            raise AuthenticationError("invalid token") from exc
        return self._claims.principal(claims)
