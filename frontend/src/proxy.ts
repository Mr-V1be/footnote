import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/server/auth/cookie";

/**
 * Fast path for signed-out visitors: application pages need a session cookie.
 * The session itself is validated by the server when the page renders.
 */
export function proxy(request: NextRequest): NextResponse {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const login = new URL("/auth/login", request.url);
  login.searchParams.set("returnTo", request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/", "/o/:path*", "/platform", "/platform/:path*"],
};
