import type { ApiClient } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";
import type { Billing, LedgerPage, PlanChangeResult } from "@/shared/api/types";

export const LEDGER_PAGE_SIZE = 20;

export const billingKeys = {
  overview: (organization: string) => ["organizations", organization, "billing"] as const,
  ledger: (organization: string) => [...billingKeys.overview(organization), "ledger"] as const,
};

export async function fetchLedgerPage(
  api: ApiClient,
  organization: string,
  cursor: string | null,
): Promise<LedgerPage> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/billing/ledger", {
      params: {
        path: { organization },
        query: { limit: LEDGER_PAGE_SIZE, ...(cursor ? { cursor } : {}) },
      },
    }),
  );
}

export async function fetchBilling(api: ApiClient, organization: string): Promise<Billing> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/billing", {
      params: { path: { organization } },
    }),
  );
}

export async function changePlan(
  api: ApiClient,
  organization: string,
  plan: string,
): Promise<PlanChangeResult> {
  return unwrap(
    await api.POST("/api/v1/organizations/{organization}/billing/plan", {
      params: { path: { organization } },
      body: { plan },
    }),
  );
}
