import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { MembersScreen } from "@/features/organization/members/MembersScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("members"))("title") };
}

export default function MembersPage() {
  return <MembersScreen />;
}
