"use client";

import { IconCalendarEvent } from "@tabler/icons-react";
import { useFormatter, useTranslations } from "next-intl";

import type { Billing } from "@/shared/api/types";
import { useFormatMoney } from "@/shared/format/useFormatMoney";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Meter } from "@/shared/ui/meter/Meter";
import { Notice } from "@/shared/ui/notice/Notice";

import styles from "./billing.module.css";

/** The plan in force and this month's use of each of its limits. */
export function PlanOverview({ billing }: { billing: Billing }) {
  const t = useTranslations("billing");
  const format = useFormatter();
  const money = useFormatMoney();
  const planLabel = useCodeLabel("plans");
  const metricLabel = useCodeLabel("usageMetrics");
  return (
    <section className={styles.overview} aria-label={t("current")}>
      <div className={styles.planLine}>
        <span className={styles.planName}>{planLabel(billing.plan.code)}</span>
        <span className={styles.price}>
          {billing.plan.priceKopecks === 0
            ? t("free")
            : t("perMonth", { price: money(billing.plan.priceKopecks, billing.currency) })}
        </span>
      </div>
      {billing.pendingPlan ? (
        <Notice icon={<IconCalendarEvent stroke={1.75} />} tone="ink">
          {t("pending", {
            plan: planLabel(billing.pendingPlan.code),
            date: format.dateTime(new Date(billing.periodEnd), { day: "numeric", month: "long" }),
          })}
        </Notice>
      ) : null}
      <div className={styles.meters}>
        {billing.usage.map((usage) => (
          <Meter
            key={usage.metric}
            label={metricLabel(usage.metric)}
            value={usage.used ?? 0}
            max={usage.used === null ? null : usage.limit}
            text={
              usage.used === null
                ? t("limitOnly", { limit: usage.limit })
                : t("usedOf", { used: usage.used, limit: usage.limit })
            }
          />
        ))}
      </div>
    </section>
  );
}
