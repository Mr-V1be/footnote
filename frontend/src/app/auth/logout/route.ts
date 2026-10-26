import * as client from "openid-client";
import { NextResponse, type NextRequest } from "next/server";

import { oidc } from "@/server/auth/oidc";
import { destroySession, readSession, SESSION_COOKIE } from "@/server/auth/session";
import { serverConfig } from "@/server/config";

/** Ends the local session and the identity provider session. */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const session = await readSession(request.cookies.get(SESSION_COOKIE)?.value);
  const base = serverConfig().FOOTNOTE_WEB_URL;
  let destination = new URL("/", base);
  if (session?.tokens.client === "demo") {
    // A demo session has no login page to return through: end it at the provider.
    await destroySession(session.id);
    if (session.tokens.refreshToken) {
      await client
        .tokenRevocation(await oidc("demo"), session.tokens.refreshToken)
        .catch(() => undefined);
    }
  } else if (session) {
    await destroySession(session.id);
    destination = client.buildEndSessionUrl(await oidc(), {
      post_logout_redirect_uri: `${base}/`,
      ...(session.tokens.idToken ? { id_token_hint: session.tokens.idToken } : {}),
    });
  }
  // 303 turns the form POST into a GET of the provider's logout page.
  const response = NextResponse.redirect(destination, { status: 303 });
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
