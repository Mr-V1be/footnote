import { BFF_PREFIX, type ApiClient } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";
import type {
  CheckCatalog,
  CheckReport,
  CheckRun,
  Finding,
  Quality,
  ReviewStatus,
  RunStatus,
} from "@/shared/api/types";

const PENDING: readonly RunStatus[] = ["queued", "running"];

export function isRunPending(status: RunStatus): boolean {
  return PENDING.includes(status);
}

export const checkKeys = {
  all: (organization: string) => ["organizations", organization, "checks"] as const,
  report: (organization: string, documentId: string, version: number) =>
    [...checkKeys.all(organization), "report", documentId, version] as const,
  catalog: () => ["checks", "catalog"] as const,
  quality: () => ["checks", "quality"] as const,
};

export async function fetchReport(
  api: ApiClient,
  organization: string,
  documentId: string,
  version: number,
): Promise<CheckReport | null> {
  return unwrap(
    await api.GET(
      "/api/v1/organizations/{organization}/documents/{document_id}/versions/{number}/checks/latest",
      { params: { path: { organization, document_id: documentId, number: version } } },
    ),
  );
}

export async function requestCheck(
  api: ApiClient,
  organization: string,
  documentId: string,
  version: number,
): Promise<CheckRun> {
  return unwrap(
    await api.POST(
      "/api/v1/organizations/{organization}/documents/{document_id}/versions/{number}/checks",
      { params: { path: { organization, document_id: documentId, number: version } } },
    ),
  );
}

export async function reviewFinding(
  api: ApiClient,
  organization: string,
  finding: Finding,
  review: ReviewStatus,
): Promise<Finding> {
  return unwrap(
    await api.PATCH("/api/v1/organizations/{organization}/findings/{finding_id}", {
      params: { path: { organization, finding_id: finding.id } },
      body: { review, revision: finding.revision },
    }),
  );
}

export async function fetchCheckCatalog(api: ApiClient): Promise<CheckCatalog> {
  return unwrap(await api.GET("/api/v1/checks/catalog"));
}

/** The last measurement of the checks on the reference set; null until there is one. */
export async function fetchQuality(api: ApiClient): Promise<Quality | null> {
  return unwrap(await api.GET("/api/v1/checks/quality"));
}

/** Server-sent progress of a run, through the web server like every API call. */
export function runEventsUrl(organization: string, runId: string): string {
  return `${BFF_PREFIX}/api/v1/organizations/${organization}/check-runs/${runId}/events`;
}
