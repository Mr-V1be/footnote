import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { AuditScreen } from "@/features/organization/audit/AuditScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("audit"))("title") };
}

export default function AuditPage() {
  return <AuditScreen />;
}
