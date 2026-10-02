import { redirect } from "next/navigation";

import { AccessScreen } from "@/features/access/AccessScreen";
import { serverApi } from "@/server/backend/api";
import { unwrap } from "@/shared/api/errors";

/** Entry point: the first organization of the signed-in user. */
export default async function Home() {
  const api = await serverApi("/");
  const me = unwrap(await api.GET("/api/v1/me"));
  const first = me.memberships[0];
  if (!first) return <AccessScreen reason="noOrganizations" />;
  redirect(`/o/${first.organization.alias}`);
}
