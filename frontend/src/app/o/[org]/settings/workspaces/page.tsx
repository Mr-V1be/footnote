import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { WorkspacesScreen } from "@/features/organization/workspaces/WorkspacesScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("workspaces"))("title") };
}

export default function WorkspacesPage() {
  return <WorkspacesScreen />;
}
