import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { ApiKeysScreen } from "@/features/integrations/keys/ApiKeysScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("apiKeys"))("title") };
}

export default function ApiKeysPage() {
  return <ApiKeysScreen />;
}
