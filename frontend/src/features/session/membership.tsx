"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { Membership, Permission, Workspace } from "@/shared/api/types";

export interface MembershipState {
  membership: Membership;
  workspaces: Workspace[];
}

const MembershipContext = createContext<MembershipState | null>(null);
const ScopeContext = createContext<readonly Permission[] | null>(null);

export function MembershipProvider({
  value,
  children,
}: {
  value: MembershipState;
  children: ReactNode;
}) {
  return <MembershipContext value={value}>{children}</MembershipContext>;
}

export function useMembership(): MembershipState {
  const state = useContext(MembershipContext);
  if (!state) throw new Error("useMembership must be used inside an organization");
  return state;
}

/**
 * Permissions of a narrower scope than the organization — a workspace or a
 * document — where a workspace role replaces the organization role.
 */
export function PermissionScope({
  permissions,
  children,
}: {
  permissions: readonly Permission[];
  children: ReactNode;
}) {
  return <ScopeContext value={permissions}>{children}</ScopeContext>;
}

/**
 * Permissions are computed by the server; the interface only reflects them.
 * Inside a scope its permissions apply, elsewhere the organization's.
 */
export function useCan(permission: Permission): boolean {
  const scope = useContext(ScopeContext);
  const { membership } = useMembership();
  return (scope ?? membership.permissions).includes(permission);
}
