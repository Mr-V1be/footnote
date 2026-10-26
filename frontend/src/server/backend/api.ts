import "server-only";

import createClient from "openapi-fetch";
import { redirect } from "next/navigation";
import { getLocale } from "next-intl/server";

import type { ApiClient } from "@/shared/api/client";
import type { paths } from "@/shared/api/schema";

import { currentSession } from "../auth/current";
import { accessToken } from "../auth/tokens";
import { serverConfig } from "../config";

export const BACKEND_TIMEOUT_MS = 15_000;

/**
 * API client for server components, authenticated as the signed-in user.
 * Without a usable session the user is sent to sign in. The API writes its
 * texts in the language the page is rendered in.
 */
export async function serverApi(returnTo: string): Promise<ApiClient> {
  const session = await currentSession();
  const token = session ? await accessToken(session) : null;
  if (!token) {
    redirect(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
  }
  const locale = await getLocale();
  const client = createClient<paths>({ baseUrl: serverConfig().FOOTNOTE_API_URL });
  client.use({
    onRequest({ request }) {
      request.headers.set("Authorization", `Bearer ${token}`);
      request.headers.set("Accept-Language", locale);
      return new Request(request, { signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) });
    },
  });
  return client;
}

/**
 * API client for the public endpoints (the landing's facts, the test payment
 * provider's own pages): no user, in the language the page is rendered in.
 */
export async function publicApi(): Promise<ApiClient> {
  const locale = await getLocale();
  const client = createClient<paths>({ baseUrl: serverConfig().FOOTNOTE_API_URL });
  client.use({
    onRequest({ request }) {
      request.headers.set("Accept-Language", locale);
      return new Request(request, { signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS) });
    },
  });
  return client;
}
