import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { AccessScreen } from "@/features/access/AccessScreen";
import { Landing } from "@/features/landing/Landing";
import { serverApi } from "@/server/backend/api";
import { currentSession } from "@/server/auth/current";
import { unwrap } from "@/shared/api/errors";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("landing");
  return { title: { absolute: t("metaTitle") }, description: t("metaDescription") };
}

/**
 * The product's page for guests; for a signed-in person, their first
 * organization (or the platform console for its operators).
 */
export default async function Home() {
  if (!(await currentSession())) return <Landing />;
  const api = await serverApi("/");
  const me = unwrap(await api.GET("/api/v1/me"));
  const first = me.memberships[0];
  if (!first && me.platformPermissions.length > 0) redirect("/platform");
  if (!first) return <AccessScreen reason="noOrganizations" />;
  redirect(`/o/${first.organization.alias}`);
}
