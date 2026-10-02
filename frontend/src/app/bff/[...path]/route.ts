import { type NextRequest } from "next/server";

import { readSession, SESSION_COOKIE } from "@/server/auth/session";
import { accessToken } from "@/server/auth/tokens";
import { serverConfig } from "@/server/config";

/** Only the versioned public API is reachable through the web server. */
const ALLOWED_PREFIX = "api/v1/";
const FORWARDED_REQUEST_HEADERS = [
  "content-type",
  "content-length",
  "idempotency-key",
  "accept",
  "x-request-id",
];
const FORWARDED_RESPONSE_HEADERS = [
  "content-type",
  "content-length",
  "content-disposition",
  "cache-control",
  "x-request-id",
];

function problem(status: number, code: string): Response {
  return Response.json(
    { type: "about:blank", title: code, status, code },
    { status, headers: { "content-type": "application/problem+json" } },
  );
}

async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const target = path.join("/");
  if (!target.startsWith(ALLOWED_PREFIX)) return problem(404, "not_found");

  const session = await readSession(request.cookies.get(SESSION_COOKIE)?.value);
  const token = session ? await accessToken(session) : null;
  if (!token) return problem(401, "unauthenticated");

  const headers = new Headers({ Authorization: `Bearer ${token}` });
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(
    `${serverConfig().SNOSKA_API_URL}/${target}${request.nextUrl.search}`,
    {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // Uploads are streamed through without buffering.
      ...(hasBody ? { duplex: "half" } : {}),
      cache: "no-store",
      redirect: "manual",
      // A closed tab ends the upstream request too (event streams stay open otherwise).
      signal: request.signal,
    } as RequestInit,
  );

  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
