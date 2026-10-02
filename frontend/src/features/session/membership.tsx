"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { Me, Membership, Permission, Workspace } from "@/shared/api/types";

export interface MembershipState {
  me: Me;
  membership: Membership;
  workspaces: Workspace[];
}

const MembershipContext = createContext<MembershipState | null>(null);

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

/** Permissions are computed by the server; the interface only reflects them. */
export function useCan(permission: Permission): boolean {
  return useMembership().membership.permissions.includes(permission);
}
