"use client";

import { useQuery } from "@tanstack/react-query";

import { useApi } from "@/shared/api/ApiProvider";

import { autofixKeys, fetchAutofixPreview } from "./queries";

/** What a correction of this version would do; asked only where one may be made. */
export function useAutofixPreview(
  organization: string,
  documentId: string,
  version: number,
  enabled: boolean,
) {
  const api = useApi();
  return useQuery({
    queryKey: autofixKeys.preview(organization, documentId, version),
    queryFn: () => fetchAutofixPreview(api, organization, documentId, version),
    enabled,
  });
}
