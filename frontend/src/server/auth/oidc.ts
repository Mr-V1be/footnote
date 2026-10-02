import "server-only";

import * as client from "openid-client";

import { serverConfig } from "../config";

export const SCOPES = "openid profile email organization:*";

const globalForOidc = globalThis as typeof globalThis & {
  snoskaOidc?: Promise<client.Configuration>;
};

/** Discovered Keycloak configuration for the confidential web client. */
export function oidc(): Promise<client.Configuration> {
  globalForOidc.snoskaOidc ??= (async () => {
    const config = serverConfig();
    const issuer = new URL(`${config.SNOSKA_KEYCLOAK_URL}/realms/${config.SNOSKA_KEYCLOAK_REALM}`);
    return client.discovery(
      issuer,
      config.SNOSKA_WEB_CLIENT_ID,
      config.SNOSKA_WEB_CLIENT_SECRET,
      undefined,
      // Local Keycloak is served over plain HTTP on loopback.
      issuer.protocol === "http:" ? { execute: [client.allowInsecureRequests] } : undefined,
    );
  })().catch((error: unknown) => {
    globalForOidc.snoskaOidc = undefined;
    throw error;
  });
  return globalForOidc.snoskaOidc;
}

export function callbackUrl(): string {
  return `${serverConfig().SNOSKA_WEB_URL}/auth/callback`;
}
