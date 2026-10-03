import { IconArrowRight } from "@tabler/icons-react";
import Link from "next/link";
import { getFormatter, getTranslations } from "next-intl/server";

import type { CheckCatalog, Quality } from "@/shared/api/types";

import band from "./band.module.css";
import styles from "./numbers.module.css";

/**
 * Only what is measured: the number of checks and how they did on our own
 * labelled reference set, with the way to see how it was measured.
 */
export async function Numbers({
  checks,
  quality,
}: {
  checks: CheckCatalog | null;
  quality: Quality | null;
}) {
  const t = await getTranslations("landing.numbers");
  const format = await getFormatter();
  if (!checks) return null;
  const rules = checks.checks.filter((check) => check.method === "deterministic").length;
  const legal = checks.checks.length - rules;
  const percent = (value: number | null | undefined) =>
    value === null || value === undefined ? "—" : format.number(value, { style: "percent" });
  const metrics = (method: string) =>
    quality?.methods.find((item) => item.code === method)?.metrics;
  const tiles = [
    { value: format.number(checks.checks.length), label: t("checks", { rules, legal }) },
    ...(quality
      ? [
          {
            value: percent(metrics("model")?.precision),
            label: t("legalPrecision", { recall: percent(metrics("model")?.recall) }),
          },
          {
            value: percent(metrics("deterministic")?.recall),
            label: t("rulesRecall", { precision: percent(metrics("deterministic")?.precision) }),
          },
          {
            value: format.number(quality.documents.length),
            label: t("documents"),
          },
        ]
      : []),
  ];
  return (
    <section className={`${band.band} ${band.ink}`} aria-labelledby="numbers-title">
      <div className={band.inner}>
        <header className={band.heading}>
          <p className={band.eyebrow}>{t("eyebrow")}</p>
          <h2 id="numbers-title" className={band.title}>
            {t("title")}
          </h2>
        </header>
        <dl className={styles.tiles}>
          {tiles.map((tile) => (
            <div key={tile.label} className={styles.tile}>
              <dt className={styles.label}>{tile.label}</dt>
              <dd className={styles.value}>{tile.value}</dd>
            </div>
          ))}
        </dl>
        <Link href="/how-we-check" className={styles.more}>
          {t("more")}
          <IconArrowRight stroke={1.75} aria-hidden />
        </Link>
      </div>
    </section>
  );
}
