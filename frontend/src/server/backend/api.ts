import "server-only";

import createClient from "openapi-fetch";
import { redirect } from "next/navigation";

import type { ApiClient } from "@/shared/api/client";
import type { paths } from "@/shared/api/schema";

import { currentSession } from "../auth/current";
import { accessToken } from "../auth/tokens";
import { serverConfig } from "../config";

export const BACKEND_TIMEOUT_MS = 15_000;

/**
 * API client for server components, authenticated as the signed-in user.
 * Without a usable session the user is sent to sign in.
 */
export async function serverApi(returnTo: string): Promise<ApiClient> {
  const session = await currentSession();
  const token = session ? await accessToken(session) : null;
  if (!token) {
    redirect(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
  }
  const client = createClient<paths>({ baseUrl: serverConfig().SNOSKA_API_URL });
  client.use({
    onRequest({ request }) {
      request.headers.set("Authorization", `Bearer ${token}`);
      return new Request(request, { signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) });
    },
  });
  return client;
}

/**
 * API client for the few public endpoints (the test payment provider's own
 * pages): no user, the signed token in the request is the access.
 */
export function publicApi(): ApiClient {
  const client = createClient<paths>({ baseUrl: serverConfig().SNOSKA_API_URL });
  client.use({
    onRequest({ request }) {
      return new Request(request, { signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) });
    },
  });
  return client;
}
