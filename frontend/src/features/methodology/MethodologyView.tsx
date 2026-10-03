"use client";

import { IconChartBar } from "@tabler/icons-react";
import { useFormatter, useTranslations } from "next-intl";

import type { CheckCatalog, DocumentKind, Quality } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge/Badge";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import { CheckRegistry } from "./CheckRegistry";
import styles from "./methodology.module.css";
import { ModelTrials } from "./ModelTrials";
import { QualityOverview } from "./QualityOverview";

/**
 * What the product checks, against which norms, how well it does on the
 * reference set and how its model was chosen. Shown inside an organization
 * and, the same, to guests on the public site.
 */
export function MethodologyView({
  catalog,
  quality: report,
  kinds,
}: {
  catalog: CheckCatalog;
  quality: Quality | null;
  kinds: readonly DocumentKind[];
}) {
  const t = useTranslations("methodology");
  const format = useFormatter();
  const models = catalog.models;
  return (
    <>
      <PageHeader
        title={t("title")}
        meta={
          <>
            <span>{t("checksCount", { count: catalog.checks.length })}</span>
            {report ? (
              <span>
                {t("measuredAt", {
                  date: format.dateTime(new Date(report.measuredAt), { dateStyle: "medium" }),
                })}
              </span>
            ) : null}
            <Badge tone={models.configured ? "success" : "neutral"} dot>
              {models.configured && models.languageModel
                ? t("modelConnected", { name: models.languageModel })
                : t("modelMissing")}
            </Badge>
            {report && !report.current ? <Badge tone="important">{t("stale")}</Badge> : null}
          </>
        }
      />
      <section className={styles.section} aria-labelledby="quality-heading">
        <h2 id="quality-heading" className={styles.sectionTitle}>
          {t("quality")}
        </h2>
        {report ? (
          <QualityOverview quality={report} />
        ) : (
          <StatePanel
            icon={<IconChartBar stroke={1.75} />}
            title={t("noMeasurementTitle")}
            description={t("noMeasurementDescription")}
          />
        )}
      </section>
      {report && report.trials.length > 0 ? (
        <ModelTrials trials={report.trials} chosen={report.model} />
      ) : null}
      <CheckRegistry catalog={catalog} quality={report} kinds={kinds} />
    </>
  );
}
