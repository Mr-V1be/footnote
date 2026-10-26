"""Shared actors of the integration scenarios."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import text

from footnote.bootstrap.container import Container
from footnote.domain.tenancy.members import Member
from footnote.ports.identity import OrganizationProfile
from tests.support.tokens import MemberIdentity, TokenFactory

ORG_A = OrganizationProfile(
    id=UUID("11111111-1111-4111-8111-111111111111"), alias="alpha", name="ООО «Альфа»"
)
ORG_B = OrganizationProfile(
    id=UUID("22222222-2222-4222-8222-222222222222"), alias="beta", name="АО «Бета»"
)


def _member(name: str, org: OrganizationProfile, role: str) -> MemberIdentity:
    return MemberIdentity(
        user_id=uuid4(),
        email=f"{name}@{org.alias}.example",
        name=name.title(),
        organizations={org.alias: (org.id, [role])},
    )


ALICE = _member("alice", ORG_A, "owner")
OLGA = _member("olga", ORG_A, "observer")
EVA = _member("eva", ORG_A, "executor")
BOB = _member("bob", ORG_B, "owner")
LEO = _member("leo", ORG_A, "lawyer")
MEMBERS = (ALICE, OLGA, EVA, BOB, LEO)


def member_of(identity: MemberIdentity, roles: Sequence[str]) -> Member:
    """How the identity provider lists a scenario's member."""
    first, _, last = identity.name.partition(" ")
    return Member(
        user_id=identity.user_id,
        email=identity.email,
        first_name=first,
        last_name=last,
        role_codes=frozenset(roles),
    )


def auth(tokens: TokenFactory, member: MemberIdentity) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens.token(member)}"}


async def run_jobs(container: Container) -> int:
    """Executes queued outbox jobs inline, as relay and worker would."""
    handled = 0
    while True:
        async with container.engine.begin() as connection:
            rows = (
                await connection.execute(
                    text(
                        "UPDATE outbox_messages SET dispatched_at = now() WHERE id IN "
                        "(SELECT id FROM outbox_messages WHERE dispatched_at IS NULL "
                        "AND available_at <= now() LIMIT 20) "
                        "RETURNING job_name, payload"
                    )
                )
            ).all()
        if not rows:
            return handled
        for job_name, payload in rows:
            await container.job_handlers[job_name](payload)
            handled += 1
