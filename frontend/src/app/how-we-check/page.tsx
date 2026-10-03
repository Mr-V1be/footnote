import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { publicFacts } from "@/features/landing/data";
import { MarketingShell } from "@/features/landing/MarketingShell";
import { PublicMethodology } from "@/features/landing/PublicMethodology";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("methodology"))("title") };
}

/** How the product checks, for guests: the same page as inside the product. */
export default async function HowWeCheckPage() {
  const facts = await publicFacts();
  return (
    <MarketingShell demo={facts.demo}>
      <PublicMethodology facts={facts} />
    </MarketingShell>
  );
}
