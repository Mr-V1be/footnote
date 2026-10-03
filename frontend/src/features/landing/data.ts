import "server-only";

import { publicApi } from "@/server/backend/api";
import { serverConfig } from "@/server/config";
import type { Catalog, CheckCatalog, PlansOffer, Quality } from "@/shared/api/types";

/** What the public pages show, read from the API without a user. */
export interface PublicFacts {
  checks: CheckCatalog | null;
  quality: Quality | null;
  kinds: Catalog | null;
  plans: PlansOffer | null;
  /** One-click sign-in by role is available (a demo stand). */
  demo: boolean;
}

async function attempt<T>(load: () => Promise<{ data?: T }>): Promise<T | null> {
  try {
    return (await load()).data ?? null;
  } catch {
    // The page still renders; the block that needs the data is left out.
    return null;
  }
}

export async function publicFacts(): Promise<PublicFacts> {
  const api = publicApi();
  const [checks, quality, kinds, plans] = await Promise.all([
    attempt(() => api.GET("/api/v1/checks/catalog")),
    attempt(() => api.GET("/api/v1/checks/quality")),
    attempt(() => api.GET("/api/v1/catalog")),
    attempt(() => api.GET("/api/v1/plans")),
  ]);
  return {
    checks,
    quality: (quality as Quality | null) ?? null,
    kinds,
    plans,
    demo: serverConfig().SNOSKA_DEMO_MODE,
  };
}
