"use client";

import {
  IconAlertTriangle,
  IconCircleCheck,
  IconPlugConnectedX,
  IconRefresh,
} from "@tabler/icons-react";
import { useFormatter, useTranslations } from "next-intl";

import type { CheckReport, Severity } from "@/shared/api/types";
import { Button } from "@/shared/ui/button/Button";
import { Notice } from "@/shared/ui/notice/Notice";
import { ProgressBar } from "@/shared/ui/progress/ProgressBar";

import { SEVERITIES, type RunTally } from "../findings";
import { isRunPending } from "../queries";
import { SeverityTally } from "../SeverityTally";
import styles from "./result.module.css";

/**
 * The state of the check above the document: progress while it runs, then
 * what it found in numbers and what it could not do, honestly.
 */
export function CheckSummary({
  report,
  counts,
  tally,
  reviews,
  canRecheck,
  rechecking,
  onRecheck,
}: {
  report: CheckReport | null;
  counts: Record<Severity, number>;
  tally: RunTally;
  reviews: number;
  canRecheck: boolean;
  rechecking: boolean;
  onRecheck: () => void;
}) {
  const t = useTranslations("checks");
  const format = useFormatter();
  const run = report?.run;
  const recheck = canRecheck ? (
    <Button
      variant="secondary"
      size="sm"
      icon={<IconRefresh stroke={1.75} />}
      loading={rechecking}
      onClick={onRecheck}
    >
      {t("summary.recheck")}
    </Button>
  ) : null;

  if (!run) {
    return (
      <section className={styles.summary} aria-live="polite">
        <p className={styles.summaryTitle}>{t("summary.none")}</p>
        {recheck}
      </section>
    );
  }
  if (isRunPending(run.status)) {
    const value = run.total > 0 ? run.done / run.total : undefined;
    return (
      <section className={styles.summary} data-state="running" aria-live="polite">
        <div className={styles.summaryLine}>
          <span className={styles.pulse} aria-hidden />
          <p className={styles.summaryTitle}>
            {run.status === "queued" ? t("summary.queued") : t("summary.running")}
          </p>
          {run.total > 0 ? (
            <span className={styles.progressCount}>
              {t("summary.progress", { done: run.done, total: run.total })}
            </span>
          ) : null}
        </div>
        <ProgressBar value={value} label={t("summary.running")} />
      </section>
    );
  }
  if (run.status === "failed") {
    return (
      <section className={styles.summary} data-state="failed" role="alert">
        <div className={styles.summaryLine}>
          <IconAlertTriangle stroke={1.75} className={styles.summaryIcon} aria-hidden />
          <div>
            <p className={styles.summaryTitle}>{t("summary.failed")}</p>
            <p className={styles.summaryHint}>{t("summary.failedHint")}</p>
          </div>
        </div>
        {recheck}
      </section>
    );
  }

  const outstanding = SEVERITIES.reduce((sum, severity) => sum + counts[severity], 0);
  const unavailable = tally.notPerformed - tally.modelMissing;
  // Nothing found is "clean" only when every check gave a verdict.
  const partial = tally.notPerformed > 0;
  return (
    <section className={styles.summary} data-state="completed" aria-live="polite">
      <div className={styles.summaryMain}>
        <div className={styles.summaryLine}>
          {outstanding === 0 && !partial ? (
            <IconCircleCheck stroke={1.75} className={styles.summaryClean} aria-hidden />
          ) : null}
          <p className={styles.summaryTitle}>
            {outstanding > 0
              ? t("summary.outstanding", { count: outstanding })
              : partial
                ? t("summary.cleanPartial")
                : t("summary.clean")}
          </p>
          <SeverityTally counts={counts} reviews={reviews} />
        </div>
        <p className={styles.facts}>
          {run.finishedAt ? (
            <span>
              {t("summary.completed", {
                date: format.dateTime(new Date(run.finishedAt), {
                  dateStyle: "medium",
                  timeStyle: "short",
                }),
              })}
            </span>
          ) : null}
          <span>{t("summary.passed", { count: tally.passed })}</span>
          {tally.notPerformed > 0 ? (
            <span>{t("summary.notPerformed", { count: tally.notPerformed })}</span>
          ) : null}
        </p>
        {tally.modelMissing > 0 ? (
          <Notice icon={<IconPlugConnectedX stroke={1.75} />}>{t("summary.modelMissing")}</Notice>
        ) : null}
        {unavailable > 0 ? (
          <Notice icon={<IconAlertTriangle stroke={1.75} />}>
            {t("summary.modelUnavailable")}
          </Notice>
        ) : null}
      </div>
      {recheck}
    </section>
  );
}
