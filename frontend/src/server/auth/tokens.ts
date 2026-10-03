import "server-only";

import * as client from "openid-client";

import { oidc } from "./oidc";
import type { Session, SessionTokens } from "./session";
import { storeTokens } from "./session";

/** Refresh slightly before expiry so a request never leaves with a dying token. */
const REFRESH_MARGIN_SECONDS = 30;

export function tokensFrom(
  response: client.TokenEndpointResponse & client.TokenEndpointResponseHelpers,
): SessionTokens {
  const expiresIn = response.expiresIn() ?? 60;
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token ?? null,
    idToken: response.id_token ?? null,
    expiresAt: Math.floor(Date.now() / 1000) + expiresIn,
  };
}

/** A valid access token for the session, refreshed when needed; null when the session ended. */
export async function accessToken(session: Session): Promise<string | null> {
  const now = Math.floor(Date.now() / 1000);
  if (session.tokens.expiresAt - REFRESH_MARGIN_SECONDS > now) {
    return session.tokens.accessToken;
  }
  if (!session.tokens.refreshToken) return null;
  try {
    const refreshed = tokensFrom(
      await client.refreshTokenGrant(
        await oidc(session.tokens.client ?? "web"),
        session.tokens.refreshToken,
      ),
    );
    const tokens: SessionTokens = {
      ...refreshed,
      client: session.tokens.client,
      refreshToken: refreshed.refreshToken ?? session.tokens.refreshToken,
      idToken: refreshed.idToken ?? session.tokens.idToken,
    };
    await storeTokens(session.id, tokens);
    return tokens.accessToken;
  } catch {
    return null;
  }
}
