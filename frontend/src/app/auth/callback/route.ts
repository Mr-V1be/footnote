import * as client from "openid-client";
import { NextResponse, type NextRequest } from "next/server";

import { oidc } from "@/server/auth/oidc";
import {
  createSession,
  finishLogin,
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
} from "@/server/auth/session";
import { tokensFrom } from "@/server/auth/tokens";
import { serverConfig } from "@/server/config";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const base = serverConfig().SNOSKA_WEB_URL;
  const state = request.nextUrl.searchParams.get("state");
  const transaction = state ? await finishLogin(state) : null;
  if (!state || !transaction) {
    return NextResponse.redirect(new URL("/auth/login", base));
  }
  const currentUrl = new URL(request.nextUrl.pathname + request.nextUrl.search, base);
  const response = await client.authorizationCodeGrant(await oidc(), currentUrl, {
    pkceCodeVerifier: transaction.codeVerifier,
    expectedState: state,
    expectedNonce: transaction.nonce,
  });
  const session = await createSession(tokensFrom(response));
  const redirect = NextResponse.redirect(new URL(transaction.returnTo, base));
  redirect.cookies.set(SESSION_COOKIE, session.id, {
    httpOnly: true,
    sameSite: "lax",
    secure: base.startsWith("https://"),
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
  return redirect;
}
