import type { ReactNode } from "react";

import { AccessScreen } from "@/features/access/AccessScreen";
import { PlatformShell } from "@/features/platform/PlatformShell";
import { serverApi } from "@/server/backend/api";
import { unwrap } from "@/shared/api/errors";

/** The platform console: only for those who operate the service. */
export default async function PlatformLayout({ children }: { children: ReactNode }) {
  const api = await serverApi("/platform");
  const me = unwrap(await api.GET("/api/v1/me"));
  if (me.platformPermissions.length === 0) return <AccessScreen reason="notOperator" />;
  return <PlatformShell me={me}>{children}</PlatformShell>;
}
