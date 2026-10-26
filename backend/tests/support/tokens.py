"""Signed test tokens in Keycloak's layout, verified by the real verifier."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from footnote.ports.identity import AuthenticationError

ISSUER = "http://keycloak.test/realms/footnote"
AUDIENCE = "footnote-api"
KEY_ID = "test-key"


@dataclass(frozen=True)
class MemberIdentity:
    user_id: UUID
    email: str
    name: str
    organizations: Mapping[str, tuple[UUID, Sequence[str]]]
    realm_roles: Sequence[str] = ()


class TokenFactory:
    def __init__(self) -> None:
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self._private.public_key()))
        self.public_jwk: dict[str, Any] = {
            **public_jwk,
            "kid": KEY_ID,
            "alg": "RS256",
            "use": "sig",
        }
        self.jwk = jwt.PyJWK(self.public_jwk)

    def token(self, member: MemberIdentity, *, expires_in: int = 300, **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": str(member.user_id),
            "iat": now,
            "exp": now + expires_in,
            "email": member.email,
            "name": member.name,
            "realm_access": {"roles": list(member.realm_roles)},
            "organization": {
                alias: {"id": str(org_id), "resource_access": {AUDIENCE: {"roles": list(roles)}}}
                for alias, (org_id, roles) in member.organizations.items()
            },
            **overrides,
        }
        return jwt.encode(claims, self._private, algorithm="RS256", headers={"kid": KEY_ID})


class StaticKeys:
    def __init__(self, factory: TokenFactory) -> None:
        self._key = factory.jwk

    async def key(self, kid: str) -> jwt.PyJWK:
        if kid != KEY_ID:
            raise AuthenticationError("unknown key")
        return self._key
