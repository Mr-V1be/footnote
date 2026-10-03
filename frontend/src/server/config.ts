import "server-only";

import path from "node:path";

import { loadEnvConfig } from "@next/env";
import { z } from "zod";

const schema = z.object({
  SNOSKA_WEB_URL: z.url(),
  SNOSKA_API_URL: z.url(),
  SNOSKA_KEYCLOAK_URL: z.url(),
  SNOSKA_KEYCLOAK_REALM: z.string().min(1),
  SNOSKA_WEB_CLIENT_ID: z.string().min(1).default("snoska-web"),
  SNOSKA_WEB_CLIENT_SECRET: z.string().min(1),
  SNOSKA_SESSION_SECRET: z.string().min(32),
  SNOSKA_REDIS_HOST: z.string().min(1).default("127.0.0.1"),
  SNOSKA_REDIS_PORT: z.coerce.number().int().positive().default(46311),
  SNOSKA_REDIS_PASSWORD: z.string().default(""),
});

export type ServerConfig = z.infer<typeof schema>;

let cached: ServerConfig | undefined;

/**
 * Server configuration, validated on first use (never at build time).
 * The repository keeps one .env at its root; deployed servers get real
 * environment variables, which take precedence.
 */
export function serverConfig(): ServerConfig {
  if (!cached) {
    const dev = process.env.NODE_ENV !== "production";
    // In development the server's modules are reloaded and Next may restore
    // its own environment meanwhile: read the repository's .env afresh.
    loadEnvConfig(path.resolve(process.cwd(), ".."), dev, undefined, dev);
    cached = schema.parse(process.env);
  }
  return cached;
}
