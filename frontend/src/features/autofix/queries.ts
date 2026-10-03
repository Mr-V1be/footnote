import type { ApiClient } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";
import type { AutofixPreview, AutofixResult, VersionChange } from "@/shared/api/types";

export const autofixKeys = {
  preview: (organization: string, documentId: string, version: number) =>
    ["organizations", organization, "autofix", documentId, version, "preview"] as const,
  changes: (organization: string, documentId: string, version: number) =>
    ["organizations", organization, "autofix", documentId, version, "changes"] as const,
};

const versionPath = (organization: string, documentId: string, version: number) => ({
  params: { path: { organization, document_id: documentId, number: version } },
});

export async function fetchAutofixPreview(
  api: ApiClient,
  organization: string,
  documentId: string,
  version: number,
): Promise<AutofixPreview> {
  return unwrap(
    await api.GET(
      "/api/v1/organizations/{organization}/documents/{document_id}/versions/{number}/autofix",
      versionPath(organization, documentId, version),
    ),
  );
}

export async function applyAutofix(
  api: ApiClient,
  organization: string,
  documentId: string,
  version: number,
): Promise<AutofixResult> {
  return unwrap(
    await api.POST(
      "/api/v1/organizations/{organization}/documents/{document_id}/versions/{number}/autofix",
      versionPath(organization, documentId, version),
    ),
  );
}

export async function fetchChanges(
  api: ApiClient,
  organization: string,
  documentId: string,
  version: number,
): Promise<VersionChange[]> {
  return unwrap(
    await api.GET(
      "/api/v1/organizations/{organization}/documents/{document_id}/versions/{number}/changes",
      versionPath(organization, documentId, version),
    ),
  );
}
