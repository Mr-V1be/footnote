import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { PlansScreen } from "@/features/platform/PlansScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("platform.nav"))("plans") };
}

export default function PlatformPlansPage() {
  return <PlansScreen />;
}
