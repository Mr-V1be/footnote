import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { OrganizationsScreen } from "@/features/platform/OrganizationsScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("platform.nav"))("organizations") };
}

export default function PlatformOrganizationsPage() {
  return <OrganizationsScreen />;
}
