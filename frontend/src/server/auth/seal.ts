import "server-only";

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";

import { serverConfig } from "../config";

const ALGORITHM = "aes-256-gcm";
const IV_BYTES = 12;
const TAG_BYTES = 16;

function key(): Buffer {
  return createHash("sha256").update(serverConfig().SNOSKA_SESSION_SECRET).digest();
}

/** Encrypts session data at rest: a leaked store does not leak tokens. */
export function seal(value: unknown): string {
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv(ALGORITHM, key(), iv);
  const body = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), body]).toString("base64url");
}

export function unseal<T>(sealed: string): T | null {
  try {
    const raw = Buffer.from(sealed, "base64url");
    const decipher = createDecipheriv(ALGORITHM, key(), raw.subarray(0, IV_BYTES));
    decipher.setAuthTag(raw.subarray(IV_BYTES, IV_BYTES + TAG_BYTES));
    const body = Buffer.concat([
      decipher.update(raw.subarray(IV_BYTES + TAG_BYTES)),
      decipher.final(),
    ]);
    return JSON.parse(body.toString("utf8")) as T;
  } catch {
    return null;
  }
}
