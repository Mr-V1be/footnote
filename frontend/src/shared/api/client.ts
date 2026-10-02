import createClient, { type Client } from "openapi-fetch";

import type { paths } from "./schema";

export type ApiClient = Client<paths>;

/** Prefix of the backend-for-frontend route that forwards to the API. */
export const BFF_PREFIX = "/bff";

/**
 * Browser client. Requests go to the web server, which attaches the user's
 * access token; tokens never reach the browser.
 */
export function createBrowserApi(): ApiClient {
  const client = createClient<paths>({ baseUrl: BFF_PREFIX, credentials: "same-origin" });
  client.use({
    onResponse({ response }) {
      if (response.status === 401 && typeof window !== "undefined") {
        // Sign-in is a server route, not a page: leave the application entirely.
        const login = new URL("/auth/login", window.location.origin);
        login.searchParams.set("returnTo", window.location.pathname + window.location.search);
        window.location.assign(login);
      }
      return response;
    },
  });
  return client;
}
