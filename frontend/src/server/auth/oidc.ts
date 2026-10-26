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
  footnoteOidc?: Partial<Record<OidcClient, Promise<client.Configuration>>>;
};

function credentials(kind: OidcClient): [string, string] {
  const config = serverConfig();
  return kind === "demo"
    ? [config.FOOTNOTE_DEMO_CLIENT_ID, config.FOOTNOTE_DEMO_CLIENT_SECRET]
    : [config.FOOTNOTE_WEB_CLIENT_ID, config.FOOTNOTE_WEB_CLIENT_SECRET];
}

/**
 * Keycloak's metadata read over the private network: Keycloak answers with
 * the public issuer and puts its back-channel endpoints (token, keys) on the
 * address it was asked on, so the server never goes out to the internet.
 */
async function internalConfiguration(
  internal: string,
  issuer: URL,
  [id, secret]: [string, string],
): Promise<client.Configuration> {
  const realm = issuer.pathname.split("/").pop();
  const response = await fetch(`${internal}/realms/${realm}/.well-known/openid-configuration`);
  if (!response.ok) throw new Error(`Keycloak metadata: ${response.status}`);
  const metadata = (await response.json()) as client.ServerMetadata;
  if (metadata.issuer !== issuer.href) {
    throw new Error(`Keycloak issues tokens as ${metadata.issuer}, expected ${issuer.href}`);
  }
  const configuration = new client.Configuration(metadata, id, secret);
  if (new URL(internal).protocol === "http:") client.allowInsecureRequests(configuration);
  return configuration;
}

/** Discovered Keycloak configuration for one of the web server's clients. */
export function oidc(kind: OidcClient = "web"): Promise<client.Configuration> {
  const cache = (globalForOidc.footnoteOidc ??= {});
  cache[kind] ??= (async () => {
    const config = serverConfig();
    const issuer = new URL(
      `${config.FOOTNOTE_KEYCLOAK_URL}/realms/${config.FOOTNOTE_KEYCLOAK_REALM}`,
    );
    const [id, secret] = credentials(kind);
    if (config.FOOTNOTE_KEYCLOAK_INTERNAL_URL) {
      return internalConfiguration(config.FOOTNOTE_KEYCLOAK_INTERNAL_URL, issuer, [id, secret]);
    }
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
  return `${serverConfig().FOOTNOTE_WEB_URL}/auth/callback`;
}
