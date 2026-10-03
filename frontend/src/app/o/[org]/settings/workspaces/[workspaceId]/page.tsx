import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { WorkspaceScreen } from "@/features/organization/workspaces/WorkspaceScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("workspaces"))("title") };
}

export default async function WorkspacePage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  return <WorkspaceScreen workspaceId={workspaceId} />;
}
