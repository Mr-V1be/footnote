import { IconCheck } from "@tabler/icons-react";
import Link from "next/link";
import { getFormatter, getTranslations } from "next-intl/server";

import type { PlansOffer } from "@/shared/api/types";
import { Button } from "@/shared/ui/button/Button";

import band from "./band.module.css";
import styles from "./pricing.module.css";

const KOPECKS_IN_RUBLE = 100;
/** The plan a team most often needs is marked; the order comes from the data. */
const MARKED_RANK = 1;

/** Plans as the data defines them: price and monthly limits. */
export async function Pricing({ plans, demo }: { plans: PlansOffer | null; demo: boolean }) {
  const t = await getTranslations("landing.pricing");
  const names = await getTranslations("plans");
  const metrics = await getTranslations("usageMetrics");
  const format = await getFormatter();
  if (!plans || plans.plans.length === 0) return null;
  return (
    <section id="pricing" className={band.band} aria-labelledby="pricing-title">
      <div className={band.inner}>
        <header className={band.heading}>
          <p className={band.eyebrow}>{t("eyebrow")}</p>
          <h2 id="pricing-title" className={band.title}>
            {t("title")}
          </h2>
        </header>
        <ul className={styles.plans}>
          {plans.plans.map((plan) => (
            <li
              key={plan.code}
              className={`${styles.plan} ${plan.rank === MARKED_RANK ? styles.marked : ""}`}
            >
              <h3 className={styles.name}>
                {names.has(plan.code as "start") ? names(plan.code as "start") : plan.code}
              </h3>
              <p className={styles.price}>
                {plan.priceKopecks === 0
                  ? t("free")
                  : format.number(plan.priceKopecks / KOPECKS_IN_RUBLE, {
                      style: "currency",
                      currency: plans.currency,
                      maximumFractionDigits: 0,
                    })}
                {plan.priceKopecks === 0 ? null : (
                  <span className={styles.period}> {t("month")}</span>
                )}
              </p>
              <ul className={styles.limits}>
                {Object.entries(plan.limits).map(([metric, limit]) => (
                  <li key={metric}>
                    <IconCheck stroke={2} aria-hidden />
                    <span>
                      {metrics.has(metric as "pages") ? metrics(metric as "pages") : metric}
                    </span>
                    <span className={styles.limit}>{format.number(limit)}</span>
                  </li>
                ))}
              </ul>
              <Button asChild variant={plan.rank === MARKED_RANK ? "primary" : "secondary"} block>
                <Link href={demo ? "/demo" : "/auth/login"}>{t("cta")}</Link>
              </Button>
            </li>
          ))}
        </ul>
        <p className={styles.note}>{t("note")}</p>
      </div>
    </section>
  );
}
