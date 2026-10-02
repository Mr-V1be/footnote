import "server-only";

import { randomBytes } from "node:crypto";

import { redis } from "../redis";
import { seal, unseal } from "./seal";

export { SESSION_COOKIE } from "./cookie";
/** Matches the identity provider's maximum session lifespan. */
export const SESSION_TTL_SECONDS = 10 * 60 * 60;
const LOGIN_TTL_SECONDS = 10 * 60;
const SESSION_ID_BYTES = 32;

export interface SessionTokens {
  accessToken: string;
  refreshToken: string | null;
  idToken: string | null;
  /** Unix seconds. */
  expiresAt: number;
}

export interface Session {
  id: string;
  tokens: SessionTokens;
}

export interface LoginTransaction {
  codeVerifier: string;
  nonce: string;
  returnTo: string;
}

const sessionKey = (id: string) => `snoska:web:session:${id}`;
const loginKey = (state: string) => `snoska:web:login:${state}`;

export async function createSession(tokens: SessionTokens): Promise<Session> {
  const id = randomBytes(SESSION_ID_BYTES).toString("base64url");
  await (await redis()).set(sessionKey(id), seal(tokens), { EX: SESSION_TTL_SECONDS });
  return { id, tokens };
}

export async function readSession(id: string | undefined): Promise<Session | null> {
  if (!id) return null;
  const sealed = await (await redis()).get(sessionKey(id));
  const tokens = sealed ? unseal<SessionTokens>(sealed) : null;
  return tokens ? { id, tokens } : null;
}

export async function storeTokens(id: string, tokens: SessionTokens): Promise<void> {
  await (await redis()).set(sessionKey(id), seal(tokens), { EX: SESSION_TTL_SECONDS });
}

export async function destroySession(id: string): Promise<void> {
  await (await redis()).del(sessionKey(id));
}

export async function beginLogin(state: string, transaction: LoginTransaction): Promise<void> {
  await (await redis()).set(loginKey(state), seal(transaction), { EX: LOGIN_TTL_SECONDS });
}

/** Single use: the transaction is removed as it is read. */
export async function finishLogin(state: string): Promise<LoginTransaction | null> {
  const sealed = await (await redis()).getDel(loginKey(state));
  return sealed ? unseal<LoginTransaction>(sealed) : null;
}

/** Only same-origin paths are accepted as post-login destinations. */
export function safeReturnTo(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return "/";
  }
  return value;
}
