import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { TestCheckout } from "@/features/billing/checkout/TestCheckout";
import { publicApi } from "@/server/backend/api";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("checkout"))("title"), robots: { index: false } };
}

/** The test payment provider's checkout: outside the application, like a real one. */
export default async function TestCheckoutPage({
  params,
  searchParams,
}: {
  params: Promise<{ payment: string }>;
  searchParams: Promise<{ token?: string; failed?: string }>;
}) {
  const { payment } = await params;
  const { token = "", failed } = await searchParams;
  const result = token
    ? await publicApi().GET("/api/v1/test-payments/{payment_id}", {
        params: { path: { payment_id: payment }, query: { token } },
      })
    : null;
  return (
    <TestCheckout
      paymentId={payment}
      token={token}
      payment={result?.data ?? null}
      failed={failed !== undefined}
    />
  );
}
