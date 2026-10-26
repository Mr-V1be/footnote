import "server-only";

import { createClient } from "redis";

import { serverConfig } from "./config";

function connect() {
  const config = serverConfig();
  const client = createClient({
    socket: {
      host: config.FOOTNOTE_REDIS_HOST,
      port: config.FOOTNOTE_REDIS_PORT,
      connectTimeout: 5000,
    },
    password: config.FOOTNOTE_REDIS_PASSWORD || undefined,
  });
  client.on("error", (error: unknown) => {
    console.error(JSON.stringify({ event: "redis.error", error: String(error) }));
  });
  return client.connect();
}

type RedisClient = Awaited<ReturnType<typeof connect>>;

const globalForRedis = globalThis as typeof globalThis & { footnoteRedis?: Promise<RedisClient> };

/** One connection per server process, reused across requests and hot reloads. */
export function redis(): Promise<RedisClient> {
  const existing = globalForRedis.footnoteRedis;
  if (existing) return existing;
  const created = connect();
  globalForRedis.footnoteRedis = created;
  return created;
}
