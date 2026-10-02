import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { DocumentsScreen } from "@/features/documents/list/DocumentsScreen";
import { fetchCatalog, fetchDocumentPage, queryKeys } from "@/features/documents/queries";
import { serverApi } from "@/server/backend/api";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("documents"))("title") };
}

/** Rendered with the first page already loaded; the client takes over from there. */
export default async function DocumentsPage({
  params,
  searchParams,
}: {
  params: Promise<{ org: string; workspace: string }>;
  searchParams: Promise<{ q?: string; kind?: string }>;
}) {
  const { org, workspace } = await params;
  const query = await searchParams;
  const filters = { search: query.q?.trim() ?? "", kind: query.kind ?? null };
  const api = await serverApi(`/o/${org}/w/${workspace}/documents`);
  const queryClient = new QueryClient();
  await Promise.all([
    queryClient.prefetchQuery({ queryKey: queryKeys.catalog(), queryFn: () => fetchCatalog(api) }),
    queryClient.prefetchInfiniteQuery({
      queryKey: queryKeys.list(org, workspace, filters),
      queryFn: ({ pageParam }) => fetchDocumentPage(api, org, workspace, filters, pageParam),
      initialPageParam: null as string | null,
    }),
  ]);
  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DocumentsScreen workspace={workspace} />
    </HydrationBoundary>
  );
}
