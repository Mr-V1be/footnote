import type { InfiniteData } from "@tanstack/react-query";

import { BFF_PREFIX, type ApiClient } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";
import type {
  Catalog,
  DocumentDetails,
  DocumentPage,
  DocumentStructure,
  ParseStatus,
} from "@/shared/api/types";

export interface DocumentFilters {
  search: string;
  kind: string | null;
}

export const PAGE_SIZE = 30;
/** While a version is being parsed its state is refreshed this often. */
export const PROCESSING_POLL_MS = 2000;
const PROCESSING: readonly ParseStatus[] = ["queued", "parsing"];

export function isProcessing(status: ParseStatus): boolean {
  return PROCESSING.includes(status);
}

export const queryKeys = {
  catalog: () => ["catalog"] as const,
  documents: (organization: string) => ["organizations", organization, "documents"] as const,
  list: (organization: string, workspace: string, filters: DocumentFilters) =>
    [...queryKeys.documents(organization), "list", workspace, filters] as const,
  details: (organization: string, documentId: string) =>
    [...queryKeys.documents(organization), "details", documentId] as const,
  structure: (organization: string, documentId: string, version: number) =>
    [...queryKeys.documents(organization), "structure", documentId, version] as const,
};

export async function fetchCatalog(api: ApiClient): Promise<Catalog> {
  return unwrap(await api.GET("/api/v1/catalog"));
}

export async function fetchDocumentPage(
  api: ApiClient,
  organization: string,
  workspace: string,
  filters: DocumentFilters,
  cursor: string | null,
): Promise<DocumentPage> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/workspaces/{workspace}/documents", {
      params: {
        path: { organization, workspace },
        query: {
          limit: PAGE_SIZE,
          ...(filters.search ? { q: filters.search } : {}),
          ...(filters.kind ? { kind: filters.kind } : {}),
          ...(cursor ? { cursor } : {}),
        },
      },
    }),
  );
}

export async function fetchDocument(
  api: ApiClient,
  organization: string,
  documentId: string,
): Promise<DocumentDetails> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/documents/{document_id}", {
      params: { path: { organization, document_id: documentId } },
    }),
  );
}

export async function fetchStructure(
  api: ApiClient,
  organization: string,
  documentId: string,
  version: number,
): Promise<DocumentStructure> {
  return unwrap(
    await api.GET(
      "/api/v1/organizations/{organization}/documents/{document_id}/versions/{number}/structure",
      {
        params: { path: { organization, document_id: documentId, number: version } },
      },
    ),
  );
}

export function anyProcessing(data: InfiniteData<DocumentPage> | undefined): boolean {
  return Boolean(data?.pages.some((page) => page.items.some((item) => isProcessing(item.status))));
}

export function originalFileUrl(organization: string, documentId: string, version: number): string {
  return `${BFF_PREFIX}/api/v1/organizations/${organization}/documents/${documentId}/versions/${version}/file`;
}
