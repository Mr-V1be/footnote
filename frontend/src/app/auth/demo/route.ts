import * as client from "openid-client";
import { NextResponse, type NextRequest } from "next/server";

import { oidc, SCOPES } from "@/server/auth/oidc";
import { createSession, SESSION_COOKIE, SESSION_TTL_SECONDS } from "@/server/auth/session";
import { tokensFrom } from "@/server/auth/tokens";
import { serverConfig } from "@/server/config";
import { demoAccounts } from "@/server/demo/accounts";

const SEE_OTHER = 303;

/**
 * One-click sign-in on the demo stand: the chosen role's seeded account is
 * signed in through the same identity provider and gets an ordinary session.
 * Without SNOSKA_DEMO_MODE the route does not exist.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const config = serverConfig();
  if (!config.SNOSKA_DEMO_MODE) return new NextResponse(null, { status: 404 });
  const role = String((await request.formData()).get("role") ?? "");
  const account = (await demoAccounts()).find((item) => item.role === role);
  const base = config.SNOSKA_WEB_URL;
  if (!account) return NextResponse.redirect(new URL("/demo", base), SEE_OTHER);
  try {
    const response = await client.genericGrantRequest(await oidc("demo"), "password", {
      username: account.email,
      password: account.password,
      scope: SCOPES,
    });
    const session = await createSession({ ...tokensFrom(response), client: "demo" });
    const redirect = NextResponse.redirect(new URL("/", base), SEE_OTHER);
    redirect.cookies.set(SESSION_COOKIE, session.id, {
      httpOnly: true,
      sameSite: "lax",
      secure: base.startsWith("https://"),
      path: "/",
      maxAge: SESSION_TTL_SECONDS,
    });
    return redirect;
  } catch {
    const failed = new URL("/demo", base);
    failed.searchParams.set("failed", "1");
    return NextResponse.redirect(failed, SEE_OTHER);
  }
}
