"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { queryKeys } from "@/features/documents/queries";
import { useApi } from "@/shared/api/ApiProvider";
import type { CheckReport, CheckRun, Finding, ReviewStatus } from "@/shared/api/types";

import {
  checkKeys,
  fetchReport,
  isRunPending,
  requestCheck,
  reviewFinding,
  runEventsUrl,
} from "./queries";

/** Findings of a running check are re-read at most this often. */
const REFRESH_INTERVAL_MS = 1500;
/** Without live events (the stream failed) the run is polled instead. */
const FALLBACK_POLL_MS = 3000;

/**
 * The latest check of a version, kept live while it runs.
 *
 * Progress arrives as server-sent events; each one updates the run in place
 * and, at a measured pace, re-reads the report so findings appear as their
 * checks finish. The rest of the interface is never blocked by a run.
 */
export function useCheckReport(organization: string, documentId: string, version: number | null) {
  const api = useApi();
  const queryClient = useQueryClient();
  const key = checkKeys.report(organization, documentId, version ?? 0);
  const report = useQuery({
    queryKey: key,
    queryFn: () => fetchReport(api, organization, documentId, version ?? 0),
    enabled: version !== null,
    refetchInterval: (query) => {
      const run = query.state.data?.run;
      return run && isRunPending(run.status) && query.state.fetchFailureCount > 0
        ? FALLBACK_POLL_MS
        : false;
    },
  });
  const runId = report.data?.run.id;
  const pending = report.data ? isRunPending(report.data.run.status) : false;
  const lastRefresh = useRef(0);

  useEffect(() => {
    if (!runId || !pending) return;
    const reportKey = checkKeys.report(organization, documentId, version ?? 0);
    const source = new EventSource(runEventsUrl(organization, runId));
    const refresh = () => {
      const now = Date.now();
      if (now - lastRefresh.current < REFRESH_INTERVAL_MS) return;
      lastRefresh.current = now;
      void queryClient.invalidateQueries({ queryKey: reportKey, exact: true });
    };
    source.addEventListener("run", (event) => {
      const run = JSON.parse((event as MessageEvent<string>).data) as CheckRun;
      if (!isRunPending(run.status)) {
        // The finished run comes with all its findings: re-read the report
        // rather than show it finished over the findings of a moment ago.
        lastRefresh.current = Date.now();
        void queryClient.invalidateQueries({ queryKey: reportKey, exact: true });
        return;
      }
      queryClient.setQueryData<CheckReport | null>(reportKey, (current) =>
        current && current.run.id === run.id ? { ...current, run } : current,
      );
      refresh();
    });
    source.addEventListener("end", () => {
      source.close();
      void queryClient.invalidateQueries({ queryKey: reportKey, exact: true });
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents(organization) });
    });
    return () => source.close();
  }, [organization, documentId, version, runId, pending, queryClient]);

  const recheck = useMutation({
    mutationFn: () => requestCheck(api, organization, documentId, version ?? 0),
    onSuccess: (run) => {
      queryClient.setQueryData<CheckReport | null>(key, (current) =>
        current ? { ...current, run } : current,
      );
      void queryClient.invalidateQueries({ queryKey: key, exact: true });
    },
  });

  return { report, recheck };
}

/** Review a finding optimistically; a refused change is rolled back. */
export function useFindingReview(organization: string, documentId: string, version: number) {
  const api = useApi();
  const queryClient = useQueryClient();
  const key = checkKeys.report(organization, documentId, version);
  return useMutation({
    mutationFn: ({ finding, review }: { finding: Finding; review: ReviewStatus }) =>
      reviewFinding(api, organization, finding, review),
    onMutate: async ({ finding, review }) => {
      await queryClient.cancelQueries({ queryKey: key, exact: true });
      const previous = queryClient.getQueryData<CheckReport | null>(key);
      queryClient.setQueryData<CheckReport | null>(key, (current) =>
        current ? patchFinding(current, { ...finding, review }) : current,
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      queryClient.setQueryData(key, context?.previous ?? null);
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<CheckReport | null>(key, (current) =>
        current ? patchFinding(current, saved) : current,
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents(organization) });
    },
  });
}

/** Replace the review state of one finding, keeping what only the report carries. */
function patchFinding(report: CheckReport, changed: Finding): CheckReport {
  return {
    ...report,
    findings: report.findings.map((finding) =>
      finding.id === changed.id
        ? {
            ...finding,
            review: changed.review,
            reviewedAt: changed.reviewedAt,
            revision: changed.revision,
          }
        : finding,
    ),
  };
}
