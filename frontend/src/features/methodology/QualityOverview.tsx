"use client";

import { IconRuler2, IconScale, IconStopwatch } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import type { Quality } from "@/shared/api/types";
import { ProgressBar } from "@/shared/ui/progress/ProgressBar";

import styles from "./methodology.module.css";
import { ShareValue } from "./ShareValue";
import { isMeasured, useQualityFormat, type Share } from "./useQualityFormat";

const METHODS = [
  { code: "deterministic", icon: IconRuler2 },
  { code: "model", icon: IconScale },
] as const;
const SHARES: readonly Share[] = ["precision", "recall"];

/** Precision and recall by way of checking, and how long a typical document takes. */
export function QualityOverview({ quality }: { quality: Quality }) {
  const t = useTranslations("methodology");
  const { seconds, share } = useQualityFormat();
  const typical = quality.documents.find((item) => item.typical);
  const stages = typical
    ? ([
        ["parse", typical.parseMs],
        ["rules", typical.deterministicMs],
        ["model", typical.modelMs],
        ["total", typical.totalMs],
      ] as const)
    : [];
  return (
    <div className={styles.tiles}>
      {METHODS.map(({ code, icon: Icon }) => {
        const metrics = quality.methods.find((group) => group.code === code)?.metrics;
        return (
          <article key={code} className={styles.tile}>
            <header className={styles.tileHead}>
              <Icon stroke={1.75} className={styles.tileIcon} aria-hidden />
              <div>
                <h3 className={styles.tileTitle}>{t(`method.${code}`)}</h3>
                <p className={styles.tileBasis}>{t(`methodBasis.${code}`)}</p>
              </div>
            </header>
            {isMeasured(metrics) ? (
              <dl className={styles.shares}>
                {SHARES.map((which) => {
                  const value = metrics[which];
                  return (
                    <div key={which} className={styles.shareItem}>
                      <dt>{t(which)}</dt>
                      <dd>
                        <ShareValue text={share(metrics, which)} size="lg" />
                        {value !== null ? <ProgressBar value={value} label={t(which)} /> : null}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            ) : (
              <div className={styles.unmeasured}>
                <p className={styles.unmeasuredValue}>{t("notMeasured")}</p>
                <p className={styles.unmeasuredHint}>{share(metrics, "precision").hint}</p>
              </div>
            )}
            {metrics ? (
              <p className={styles.tileFoot}>
                <span>{t("observations", { count: metrics.observations })}</span>
                {isMeasured(metrics) ? (
                  <>
                    <span>{t("falsePositives", { count: metrics.falsePositives })}</span>
                    <span>{t("misses", { count: metrics.falseNegatives })}</span>
                    {metrics.reviews > 0 ? (
                      <span>{t("reviews", { count: metrics.reviews })}</span>
                    ) : null}
                  </>
                ) : null}
              </p>
            ) : null}
          </article>
        );
      })}
      {typical ? (
        <article className={styles.tile}>
          <header className={styles.tileHead}>
            <IconStopwatch stroke={1.75} className={styles.tileIcon} aria-hidden />
            <div>
              <h3 className={styles.tileTitle}>{t("timing")}</h3>
              <p className={styles.tileBasis}>{t("typical", { pages: typical.pages })}</p>
            </div>
          </header>
          <dl className={styles.stages}>
            {stages.map(([stage, milliseconds]) => (
              <div key={stage} className={styles.stage} data-stage={stage}>
                <dt>{t(`stage.${stage}`)}</dt>
                <dd data-empty={milliseconds === null || undefined}>{seconds(milliseconds)}</dd>
              </div>
            ))}
          </dl>
          <p className={styles.tileFoot}>
            <span>{t("referenceSet", { count: quality.documents.length })}</span>
          </p>
        </article>
      ) : null}
    </div>
  );
}
