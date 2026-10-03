import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { BillingScreen } from "@/features/billing/BillingScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("billing"))("title") };
}

export default function BillingPage() {
  return <BillingScreen />;
}
