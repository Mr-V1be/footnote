import type { ApiClient } from "@/shared/api/client";
import { unwrap, unwrapEmpty } from "@/shared/api/errors";
import type { OrganizationRow, Plan, SystemStatus } from "@/shared/api/types";

export const platformKeys = {
  organizations: () => ["platform", "organizations"] as const,
  plans: () => ["platform", "plans"] as const,
  system: () => ["platform", "system"] as const,
};

export async function fetchOrganizationRows(api: ApiClient): Promise<OrganizationRow[]> {
  return unwrap(await api.GET("/api/v1/platform/organizations/overview"));
}

export async function fetchPlatformPlans(api: ApiClient): Promise<Plan[]> {
  return unwrap(await api.GET("/api/v1/platform/plans"));
}

export async function assignPlan(
  api: ApiClient,
  organizationId: string,
  plan: string,
): Promise<void> {
  unwrapEmpty(
    await api.PUT("/api/v1/platform/organizations/{organization_id}/plan", {
      params: { path: { organization_id: organizationId } },
      body: { plan },
    }),
  );
}

export async function fetchSystemStatus(api: ApiClient): Promise<SystemStatus> {
  return unwrap(await api.GET("/api/v1/platform/system"));
}

export async function watchCorpusNow(api: ApiClient): Promise<void> {
  unwrapEmpty(await api.POST("/api/v1/platform/corpus/watch"));
}
