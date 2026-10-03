import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { DemoChooser } from "@/features/demo/DemoChooser";
import { MarketingShell } from "@/features/landing/MarketingShell";
import { demoAccounts } from "@/server/demo/accounts";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("demo"))("title") };
}

/** One-click sign-in by role; exists only on a demo stand. */
export default async function DemoPage({
  searchParams,
}: {
  searchParams: Promise<{ failed?: string }>;
}) {
  const accounts = await demoAccounts();
  if (accounts.length === 0) notFound();
  const { failed } = await searchParams;
  return (
    <MarketingShell demo>
      <DemoChooser accounts={accounts} failed={failed !== undefined} />
    </MarketingShell>
  );
}
