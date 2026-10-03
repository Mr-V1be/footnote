import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { WebhookScreen } from "@/features/integrations/webhooks/WebhookScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("webhooks"))("title") };
}

export default async function WebhookPage({ params }: { params: Promise<{ endpointId: string }> }) {
  const { endpointId } = await params;
  return <WebhookScreen endpointId={endpointId} />;
}
