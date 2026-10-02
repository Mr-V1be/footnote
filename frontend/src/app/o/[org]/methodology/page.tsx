import { dehydrate, HydrationBoundary, QueryClient } from "@tanstack/react-query";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { checkKeys, fetchCheckCatalog, fetchQuality } from "@/features/checks/queries";
import { fetchCatalog, queryKeys } from "@/features/documents/queries";
import { MethodologyScreen } from "@/features/methodology/MethodologyScreen";
import { serverApi } from "@/server/backend/api";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("methodology"))("title") };
}

export default async function MethodologyPage({ params }: { params: Promise<{ org: string }> }) {
  const { org } = await params;
  const api = await serverApi(`/o/${org}/methodology`);
  const queryClient = new QueryClient();
  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: checkKeys.catalog(),
      queryFn: () => fetchCheckCatalog(api),
    }),
    queryClient.prefetchQuery({ queryKey: checkKeys.quality(), queryFn: () => fetchQuality(api) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.catalog(), queryFn: () => fetchCatalog(api) }),
  ]);
  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <MethodologyScreen />
    </HydrationBoundary>
  );
}
