import "server-only";

import { cookies } from "next/headers";

import { readSession, SESSION_COOKIE, type Session } from "./session";

export async function currentSession(): Promise<Session | null> {
  const store = await cookies();
  return readSession(store.get(SESSION_COOKIE)?.value);
}
