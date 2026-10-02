import type { ReactNode } from "react";

import { AccessScreen } from "@/features/access/AccessScreen";
import { AppShell } from "@/features/shell/AppShell";
import { serverApi } from "@/server/backend/api";
import { ApiError, unwrap } from "@/shared/api/errors";

export default async function OrganizationLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ org: string }>;
}) {
  const { org } = await params;
  const api = await serverApi(`/o/${org}`);
  const me = unwrap(await api.GET("/api/v1/me"));
  const membership = me.memberships.find((item) => item.organization.alias === org);
  if (!membership) return <AccessScreen reason="notMember" />;
  const workspaces = await api
    .GET("/api/v1/organizations/{organization}/workspaces", {
      params: { path: { organization: org } },
    })
    .then(unwrap)
    .catch((error: unknown) => {
      if (error instanceof ApiError && error.isForbidden) return null;
      throw error;
    });
  if (!workspaces) return <AccessScreen reason="notMember" />;
  return <AppShell state={{ me, membership, workspaces }}>{children}</AppShell>;
}
