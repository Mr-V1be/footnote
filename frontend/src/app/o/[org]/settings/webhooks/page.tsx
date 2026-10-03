import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { WebhooksScreen } from "@/features/integrations/webhooks/WebhooksScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("webhooks"))("title") };
}

export default function WebhooksPage() {
  return <WebhooksScreen />;
}
