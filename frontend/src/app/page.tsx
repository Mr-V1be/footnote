import { redirect } from "next/navigation";

import { AccessScreen } from "@/features/access/AccessScreen";
import { serverApi } from "@/server/backend/api";
import { unwrap } from "@/shared/api/errors";

/** Entry point: the first organization of the signed-in user, or the platform console. */
export default async function Home() {
  const api = await serverApi("/");
  const me = unwrap(await api.GET("/api/v1/me"));
  const first = me.memberships[0];
  // An operator of the platform without an organization of their own.
  if (!first && me.platformPermissions.length > 0) redirect("/platform");
  if (!first) return <AccessScreen reason="noOrganizations" />;
  redirect(`/o/${first.organization.alias}`);
}
