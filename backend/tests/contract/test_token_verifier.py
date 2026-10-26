from __future__ import annotations

from uuid import uuid4

import httpx
import jwt
import pytest
import respx

from footnote.infrastructure.identity.claims import KeycloakClaimsMapper
from footnote.infrastructure.identity.jwks import JwksKeySource
from footnote.infrastructure.identity.jwt_verifier import JwtTokenVerifier, TokenPolicy
from footnote.ports.identity import AuthenticationError
from tests.support.tokens import AUDIENCE, ISSUER, KEY_ID, MemberIdentity, StaticKeys, TokenFactory

FACTORY = TokenFactory()
ORG = uuid4()
MEMBER = MemberIdentity(
    user_id=uuid4(),
    email="orlov@acme.example",
    name="Михаил Орлов",
    organizations={"acme": (ORG, ["lawyer"])},
    realm_roles=["platform-admin", "offline_access"],
)


def verifier() -> JwtTokenVerifier:
    return JwtTokenVerifier(
        StaticKeys(FACTORY),
        TokenPolicy(issuer=ISSUER, audience=AUDIENCE),
        KeycloakClaimsMapper(AUDIENCE),
    )


async def test_keycloak_organization_claim_becomes_memberships() -> None:
    principal = await verifier().verify(FACTORY.token(MEMBER))
    assert principal.user_id == MEMBER.user_id
    assert principal.display_name == "Михаил Орлов"
    [membership] = principal.memberships
    assert (membership.organization_id, membership.organization_alias) == (ORG, "acme")
    assert membership.role_codes == {"lawyer"}
    assert "platform-admin" in principal.platform_role_codes


@pytest.mark.parametrize(
    "overrides",
    [{"aud": "another-api"}, {"iss": "http://evil.test/realms/snoska"}],
)
async def test_foreign_audience_or_issuer_is_rejected(overrides: dict[str, str]) -> None:
    with pytest.raises(AuthenticationError):
        await verifier().verify(FACTORY.token(MEMBER, **overrides))


async def test_expired_token_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="expired"):
        await verifier().verify(FACTORY.token(MEMBER, expires_in=-120))


async def test_token_signed_by_another_key_is_rejected() -> None:
    forged = TokenFactory().token(MEMBER)
    with pytest.raises(AuthenticationError):
        await verifier().verify(forged)


@respx.mock
async def test_jwks_source_refreshes_on_unknown_key_with_rate_limit() -> None:
    jwks_url = f"{ISSUER}/protocol/openid-connect/certs"
    route = respx.get(jwks_url).mock(
        return_value=httpx.Response(200, json={"keys": [FACTORY.public_jwk]})
    )
    async with httpx.AsyncClient() as client:
        source = JwksKeySource(client, jwks_url, min_refresh_interval=3600)
        assert isinstance(await source.key(KEY_ID), jwt.PyJWK)
        with pytest.raises(AuthenticationError):
            await source.key("rotated-away")
    assert route.call_count == 1


@respx.mock
async def test_jwks_source_fetches_keys_right_after_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    # Monotonic time counts from boot: a fresh host must still load the keys.
    monkeypatch.setattr("footnote.infrastructure.identity.jwks.time.monotonic", lambda: 5.0)
    jwks_url = f"{ISSUER}/protocol/openid-connect/certs"
    respx.get(jwks_url).mock(return_value=httpx.Response(200, json={"keys": [FACTORY.public_jwk]}))
    async with httpx.AsyncClient() as client:
        source = JwksKeySource(client, jwks_url, min_refresh_interval=3600)
        assert isinstance(await source.key(KEY_ID), jwt.PyJWK)
