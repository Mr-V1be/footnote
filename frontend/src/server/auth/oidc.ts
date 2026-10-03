import "server-only";

import * as client from "openid-client";

import { serverConfig } from "../config";

export const SCOPES = "openid profile email organization:*";

/**
 * The confidential clients the web server signs in with: `web` for the usual
 * authorization code flow, `demo` for one-click sign-in on the demo stand.
 */
export type OidcClient = "web" | "demo";

const globalForOidc = globalThis as typeof globalThis & {
  snoskaOidc?: Partial<Record<OidcClient, Promise<client.Configuration>>>;
};

function credentials(kind: OidcClient): [string, string] {
  const config = serverConfig();
  return kind === "demo"
    ? [config.SNOSKA_DEMO_CLIENT_ID, config.SNOSKA_DEMO_CLIENT_SECRET]
    : [config.SNOSKA_WEB_CLIENT_ID, config.SNOSKA_WEB_CLIENT_SECRET];
}

/** Discovered Keycloak configuration for one of the web server's clients. */
export function oidc(kind: OidcClient = "web"): Promise<client.Configuration> {
  const cache = (globalForOidc.snoskaOidc ??= {});
  cache[kind] ??= (async () => {
    const config = serverConfig();
    const issuer = new URL(`${config.SNOSKA_KEYCLOAK_URL}/realms/${config.SNOSKA_KEYCLOAK_REALM}`);
    const [id, secret] = credentials(kind);
    return client.discovery(
      issuer,
      id,
      secret,
      undefined,
      // Local Keycloak is served over plain HTTP on loopback.
      issuer.protocol === "http:" ? { execute: [client.allowInsecureRequests] } : undefined,
    );
  })().catch((error: unknown) => {
    cache[kind] = undefined;
    throw error;
  });
  return cache[kind];
}

export function callbackUrl(): string {
  return `${serverConfig().SNOSKA_WEB_URL}/auth/callback`;
}
