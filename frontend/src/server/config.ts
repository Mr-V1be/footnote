import "server-only";

import path from "node:path";

import { loadEnvConfig } from "@next/env";
import { z } from "zod";

const schema = z.object({
  FOOTNOTE_WEB_URL: z.url(),
  FOOTNOTE_API_URL: z.url(),
  FOOTNOTE_KEYCLOAK_URL: z.url(),
  // Where the web server reaches Keycloak inside a private network; the
  // public URL stays the issuer. Empty: the public URL serves both.
  FOOTNOTE_KEYCLOAK_INTERNAL_URL: z.union([z.url(), z.literal("")]).default(""),
  FOOTNOTE_KEYCLOAK_REALM: z.string().min(1),
  FOOTNOTE_WEB_CLIENT_ID: z.string().min(1).default("footnote-web"),
  FOOTNOTE_WEB_CLIENT_SECRET: z.string().min(1),
  FOOTNOTE_SESSION_SECRET: z.string().min(32),
  FOOTNOTE_REDIS_HOST: z.string().min(1).default("127.0.0.1"),
  FOOTNOTE_REDIS_PORT: z.coerce.number().int().positive().default(46311),
  FOOTNOTE_REDIS_PASSWORD: z.string().default(""),
  // The demo stand: one-click sign-in by role. Off unless set to "true".
  FOOTNOTE_DEMO_MODE: z
    .enum(["true", "false"])
    .default("false")
    .transform((value) => value === "true"),
  FOOTNOTE_DEMO_CLIENT_ID: z.string().min(1).default("footnote-demo"),
  FOOTNOTE_DEMO_CLIENT_SECRET: z.string().default(""),
  // The seed file names the account each role opens.
  FOOTNOTE_DEMO_SEED: z.string().default(path.resolve(process.cwd(), "../backend/demo/seed.yaml")),
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
