from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from snoska.application.audit.trail import AuditTrail
from snoska.application.billing.meter import UsageMeter
from snoska.domain.audit.event import AuditAction, AuditTarget
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.members import (
    Member,
    MemberNotFoundError,
    ensure_not_protected,
    ensure_owner_remains,
    require_role,
)
from snoska.domain.tenancy.permissions import Permission
from snoska.domain.tenancy.roles import RoleCatalog
from snoska.ports.identity import Invitation, MemberAdministration, OrganizationDirectory
from snoska.ports.unit_of_work import UnitOfWorkFactory


def _target(member: Member) -> AuditTarget:
    return AuditTarget(type="member", id=str(member.user_id), label=member.display_name)


class OrganizationMembers:
    """Who belongs to an organization and with which role.

    Membership lives in the identity provider; this use case checks the
    rules (a known role, an owner always remains) and records the change in
    the audit log once the provider has accepted it.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        directory: OrganizationDirectory,
        administration: MemberAdministration,
        roles: RoleCatalog,
        audit: AuditTrail,
        meter: UsageMeter,
        protected_emails: frozenset[str] = frozenset(),
    ) -> None:
        self._uow_factory = uow_factory
        self._directory = directory
        self._administration = administration
        self._roles = roles
        self._audit = audit
        self._meter = meter
        # Demo sign-in accounts (demo stands only): their roles stay as seeded.
        self._protected = frozenset(email.casefold() for email in protected_emails)

    async def list(self, access: OrganizationAccess) -> Sequence[Member]:
        access.require(Permission.MEMBERS_MANAGE)
        members = await self._directory.list_members(access.organization_id)
        return sorted(members, key=lambda member: member.display_name.casefold())

    async def invite(self, access: OrganizationAccess, invitation: Invitation) -> Member:
        access.require(Permission.MEMBERS_MANAGE)
        require_role(self._roles, invitation.role_code)
        members = await self._directory.list_members(access.organization_id)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            # The plan caps the number of members.
            await self._meter.ensure_members(uow, access.organization_id, len(members))
            await uow.commit()
        user_id = await self._administration.invite(access.organization_id, invitation)
        member = Member(
            user_id=user_id,
            email=invitation.email,
            first_name=invitation.first_name,
            last_name=invitation.last_name,
            role_codes=frozenset({invitation.role_code}),
            pending=True,
        )
        await self._record(
            access, AuditAction.MEMBER_INVITED, member, {"role": invitation.role_code}
        )
        return member

    async def change_role(
        self, access: OrganizationAccess, user_id: UUID, role_code: str
    ) -> Member:
        access.require(Permission.MEMBERS_MANAGE)
        require_role(self._roles, role_code)
        members = await self._directory.list_members(access.organization_id)
        member = self._find(members, user_id)
        ensure_not_protected(member, self._protected)
        ensure_owner_remains(members, user_id, new_role=role_code)
        await self._administration.set_role(access.organization_id, user_id, role_code)
        await self._record(
            access,
            AuditAction.MEMBER_ROLE_CHANGED,
            member,
            {"from": ",".join(sorted(member.role_codes)), "to": role_code},
        )
        return Member(
            user_id=member.user_id,
            email=member.email,
            first_name=member.first_name,
            last_name=member.last_name,
            role_codes=frozenset({role_code}),
            pending=member.pending,
        )

    async def remove(self, access: OrganizationAccess, user_id: UUID) -> None:
        access.require(Permission.MEMBERS_MANAGE)
        members = await self._directory.list_members(access.organization_id)
        member = self._find(members, user_id)
        ensure_not_protected(member, self._protected)
        ensure_owner_remains(members, user_id, new_role=None)
        await self._administration.remove(access.organization_id, user_id)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await uow.workspace_members.remove_user(user_id)
            await self._audit.record(uow, access, AuditAction.MEMBER_REMOVED, _target(member))
            await uow.commit()

    async def _record(
        self,
        access: OrganizationAccess,
        action: AuditAction,
        member: Member,
        details: dict[str, str],
    ) -> None:
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            await self._audit.record(uow, access, action, _target(member), details)
            await uow.commit()

    @staticmethod
    def _find(members: Sequence[Member], user_id: UUID) -> Member:
        member = next((item for item in members if item.user_id == user_id), None)
        if member is None:
            raise MemberNotFoundError("not a member of the organization")
        return member
