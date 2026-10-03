"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { Me, Permission } from "@/shared/api/types";

const SessionContext = createContext<Me | null>(null);

/** The signed-in person, available on every page of the application. */
export function SessionProvider({ me, children }: { me: Me; children: ReactNode }) {
  return <SessionContext value={me}>{children}</SessionContext>;
}

export function useSession(): Me {
  const me = useContext(SessionContext);
  if (!me) throw new Error("useSession must be used inside SessionProvider");
  return me;
}

/** Permissions on the platform as a whole (operators of the service). */
export function usePlatformCan(permission: Permission): boolean {
  return useSession().platformPermissions.includes(permission);
}

/** Whether the person operates the platform at all. */
export function useIsOperator(): boolean {
  return useSession().platformPermissions.length > 0;
}
