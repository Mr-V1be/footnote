import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SystemScreen } from "@/features/platform/SystemScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("platform.nav"))("system") };
}

export default function PlatformSystemPage() {
  return <SystemScreen />;
}
