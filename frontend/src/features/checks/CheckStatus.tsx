"use client";

import { useTranslations } from "next-intl";

import { StatusBadge } from "@/features/documents/StatusBadge";
import type { DocumentListItem } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge/Badge";
import { Tooltip } from "@/shared/ui/tooltip/Tooltip";

import { isRunPending } from "./queries";
import { SeverityTally } from "./SeverityTally";

/**
 * Where a document stands, in one cell of a list: being read, being
 * checked, or what the latest check of its latest version found.
 */
export function CheckStatus({ item }: { item: DocumentListItem }) {
  const t = useTranslations("checks.status");
  const run = item.check;
  if (item.status !== "parsed")
    return <StatusBadge status={item.status} failure={item.failureCode} />;
  if (!run) return <Badge>{t("unchecked")}</Badge>;
  if (isRunPending(run.status)) {
    return (
      <Badge tone="ink" dot pulse>
        {run.status === "running" && run.total > 0
          ? t("running", { done: run.done, total: run.total })
          : t("queued")}
      </Badge>
    );
  }
  if (run.status === "failed") return <Badge tone="critical">{t("failed")}</Badge>;
  const counts = { critical: run.critical, important: run.important, advice: run.advice };
  if (run.critical + run.important + run.advice + run.reviews === 0) {
    // Nothing found is "clean" only when every check gave a verdict.
    if (run.notPerformed > 0) {
      return (
        <Tooltip content={t("partialHint", { count: run.notPerformed })}>
          <span tabIndex={0} aria-label={t("partialHint", { count: run.notPerformed })}>
            <Badge dot>{t("partial")}</Badge>
          </span>
        </Tooltip>
      );
    }
    return (
      <Badge tone="success" dot>
        {t("clean")}
      </Badge>
    );
  }
  return <SeverityTally counts={counts} reviews={run.reviews} variant="compact" />;
}
