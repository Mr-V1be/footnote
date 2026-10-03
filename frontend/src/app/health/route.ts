/** Liveness of the web server for the container's health check. */
export const dynamic = "force-dynamic";

export function GET(): Response {
  return new Response("ok", { headers: { "Cache-Control": "no-store" } });
}
