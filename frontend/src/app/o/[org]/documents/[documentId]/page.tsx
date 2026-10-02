import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import type { Metadata } from "next";

import { fetchDocument, fetchStructure, queryKeys } from "@/features/documents/queries";
import { DocumentScreen } from "@/features/documents/viewer/DocumentScreen";
import { serverApi } from "@/server/backend/api";
import { ApiError } from "@/shared/api/errors";

type Params = Promise<{ org: string; documentId: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { org, documentId } = await params;
  try {
    const document = await fetchDocument(
      await serverApi(`/o/${org}/documents/${documentId}`),
      org,
      documentId,
    );
    return { title: document.title };
  } catch {
    return {};
  }
}

export default async function DocumentPage({
  params,
  searchParams,
}: {
  params: Params;
  searchParams: Promise<{ v?: string }>;
}) {
  const { org, documentId } = await params;
  const { v } = await searchParams;
  const api = await serverApi(`/o/${org}/documents/${documentId}`);
  const queryClient = new QueryClient();
  try {
    const document = await queryClient.fetchQuery({
      queryKey: queryKeys.details(org, documentId),
      queryFn: () => fetchDocument(api, org, documentId),
    });
    const requested = Number(v);
    const version = document.versions.some((item) => item.number === requested)
      ? requested
      : document.latestVersion;
    await queryClient.prefetchQuery({
      queryKey: queryKeys.structure(org, documentId, version),
      queryFn: () => fetchStructure(api, org, documentId, version),
    });
  } catch (error) {
    // A missing document is rendered by the client screen as a "not found" state.
    if (!(error instanceof ApiError)) throw error;
  }
  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DocumentScreen documentId={documentId} />
    </HydrationBoundary>
  );
}
