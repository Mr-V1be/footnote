import { redirect } from "next/navigation";

import { serverApi } from "@/server/backend/api";
import { unwrap } from "@/shared/api/errors";

/** An organization opens on the documents of its first workspace. */
export default async function OrganizationHome({ params }: { params: Promise<{ org: string }> }) {
  const { org } = await params;
  const api = await serverApi(`/o/${org}`);
  const workspaces = unwrap(
    await api.GET("/api/v1/organizations/{organization}/workspaces", {
      params: { path: { organization: org } },
    }),
  );
  const first = workspaces[0];
  redirect(first ? `/o/${org}/w/${first.slug}/documents` : "/");
}
