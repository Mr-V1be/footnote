import * as client from "openid-client";
import { NextResponse, type NextRequest } from "next/server";
import { getLocale } from "next-intl/server";

import { oidc, callbackUrl, SCOPES } from "@/server/auth/oidc";
import { beginLogin, safeReturnTo } from "@/server/auth/session";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const config = await oidc();
  const codeVerifier = client.randomPKCECodeVerifier();
  const state = client.randomState();
  const nonce = client.randomNonce();
  await beginLogin(state, {
    codeVerifier,
    nonce,
    returnTo: safeReturnTo(request.nextUrl.searchParams.get("returnTo")),
  });
  const url = client.buildAuthorizationUrl(config, {
    redirect_uri: callbackUrl(),
    scope: SCOPES,
    state,
    nonce,
    code_challenge: await client.calculatePKCECodeChallenge(codeVerifier),
    code_challenge_method: "S256",
    // The sign-in pages speak the language the visitor reads the product in.
    ui_locales: await getLocale(),
  });
  return NextResponse.redirect(url);
}
