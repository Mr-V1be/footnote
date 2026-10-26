import { NextResponse, type NextRequest } from "next/server";

import { publicApi } from "@/server/backend/api";
import { serverConfig } from "@/server/config";

const SEE_OTHER = 303;

/**
 * The test checkout's decision: tell the provider, then go back to the
 * service — only to the service's own address, whatever the provider says.
 */
export async function POST(
  request: NextRequest,
  context: { params: Promise<{ payment: string }> },
): Promise<NextResponse> {
  const { payment } = await context.params;
  const form = await request.formData();
  const token = String(form.get("token") ?? "");
  const succeeded = form.get("decision") === "pay";
  const api = await publicApi();
  const result = await api.POST("/api/v1/test-payments/{payment_id}/decision", {
    params: { path: { payment_id: payment } },
    body: { token, succeeded },
  });
  const web = serverConfig().FOOTNOTE_WEB_URL;
  if (!result.data) {
    const back = new URL(`/pay/test/${encodeURIComponent(payment)}`, web);
    back.searchParams.set("token", token);
    back.searchParams.set("failed", "1");
    return NextResponse.redirect(back, SEE_OTHER);
  }
  const target = new URL(result.data.returnUrl);
  if (target.origin !== new URL(web).origin)
    return NextResponse.redirect(new URL("/", web), SEE_OTHER);
  target.searchParams.set("payment", succeeded ? "succeeded" : "declined");
  return NextResponse.redirect(target, SEE_OTHER);
}
