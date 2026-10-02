"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useCallback } from "react";

import type { QualityMetrics } from "@/shared/api/types";

/** Below this a stage reads as "under 0.01 s" rather than "0.00 s". */
const SMALLEST_MS = 10;
const MS_PER_SECOND = 1000;

export type Share = "precision" | "recall";

/** The checks of a group ran during the measurement, so their shares mean something. */
export function isMeasured(metrics: QualityMetrics | undefined): metrics is QualityMetrics {
  return metrics !== undefined && metrics.errors < metrics.observations;
}

/** What a share of a group of observations reads as, and why when it has no number. */
export interface ShareText {
  value: string;
  hint: string | null;
}

export function useQualityFormat() {
  const t = useTranslations("methodology");
  const format = useFormatter();

  const seconds = useCallback(
    (milliseconds: number | null) => {
      if (milliseconds === null) return t("notMeasured");
      const fixed = { minimumFractionDigits: 2, maximumFractionDigits: 2 };
      if (milliseconds < SMALLEST_MS) {
        return t("underSeconds", { value: format.number(SMALLEST_MS / MS_PER_SECOND, fixed) });
      }
      return t("seconds", { value: format.number(milliseconds / MS_PER_SECOND, fixed) });
    },
    [t, format],
  );

  const share = useCallback(
    (metrics: QualityMetrics | undefined, which: Share): ShareText => {
      // A check added after the measurement has no numbers yet.
      if (!metrics) return { value: t("notMeasured"), hint: t("stale") };
      if (metrics.errors === metrics.observations) {
        return { value: t("notMeasured"), hint: t("notMeasuredHint") };
      }
      const value = metrics[which];
      if (value === null) {
        return {
          value: t("noCases"),
          hint: which === "precision" ? t("noCasesPrecision") : t("noCasesRecall"),
        };
      }
      return {
        value: format.number(value, { style: "percent", maximumFractionDigits: 0 }),
        hint: null,
      };
    },
    [t, format],
  );

  return { seconds, share };
}
