"use client";

import { useTranslations } from "next-intl";
import { VisuallyHidden } from "radix-ui";

import type { Severity } from "@/shared/api/types";

import { SEVERITIES } from "./findings";
import styles from "./severity-tally.module.css";

/**
 * Outstanding findings by severity, and those waiting for a lawyer. In full
 * the counts are spelled out; compact shows the numbers in the colours of
 * their severity and keeps the words for screen readers.
 */
export function SeverityTally({
  counts,
  reviews,
  variant = "full",
}: {
  counts: Record<Severity, number>;
  reviews: number;
  variant?: "full" | "compact";
}) {
  const t = useTranslations("checks");
  const items = [
    ...SEVERITIES.filter((severity) => counts[severity] > 0).map((severity) => ({
      key: severity,
      count: counts[severity],
      label: t(`severityCount.${severity}`, { count: counts[severity] }),
    })),
    ...(reviews > 0
      ? [{ key: "review", count: reviews, label: t("summary.reviews", { count: reviews }) }]
      : []),
  ];
  if (items.length === 0) return null;
  return (
    <ul className={styles.tally} data-variant={variant}>
      {items.map((item) => (
        <li key={item.key} data-severity={item.key}>
          {variant === "compact" ? (
            <>
              <span aria-hidden>{item.count}</span>
              <VisuallyHidden.Root>{item.label}</VisuallyHidden.Root>
            </>
          ) : (
            item.label
          )}
        </li>
      ))}
    </ul>
  );
}
