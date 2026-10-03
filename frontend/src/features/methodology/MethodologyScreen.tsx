"use client";

import { IconAlertTriangle, IconChartBar } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { checkKeys, fetchCheckCatalog, fetchQuality } from "@/features/checks/queries";
import { fetchCatalog, queryKeys } from "@/features/documents/queries";
import { useApi } from "@/shared/api/ApiProvider";
import { Badge } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import { CheckRegistry } from "./CheckRegistry";
import styles from "./methodology.module.css";
import { QualityOverview } from "./QualityOverview";

/** What the product checks, against which norms, and how well it does on the reference set. */
export function MethodologyScreen() {
  const t = useTranslations("methodology");
  const tc = useTranslations("common");
  const format = useFormatter();
  const api = useApi();
  const catalog = useQuery({
    queryKey: checkKeys.catalog(),
    queryFn: () => fetchCheckCatalog(api),
    staleTime: Infinity,
  });
  const quality = useQuery({ queryKey: checkKeys.quality(), queryFn: () => fetchQuality(api) });
  const kinds = useQuery({
    queryKey: queryKeys.catalog(),
    queryFn: () => fetchCatalog(api),
    staleTime: Infinity,
  });

  if (catalog.isError || quality.isError) {
    return (
      <Page spacing="lg">
        <PageHeader title={t("title")} />
        <StatePanel
          icon={<IconAlertTriangle stroke={1.75} />}
          tone="critical"
          role="alert"
          title={t("errorTitle")}
          description={t("errorDescription")}
          action={
            <Button
              variant="secondary"
              onClick={() => void Promise.all([catalog.refetch(), quality.refetch()])}
            >
              {tc("retry")}
            </Button>
          }
        />
      </Page>
    );
  }
  if (!catalog.data || quality.isPending) return <MethodologySkeleton />;

  const report = quality.data;
  const models = catalog.data.models;
  return (
    <Page spacing="lg">
      <PageHeader
        title={t("title")}
        meta={
          <>
            <span>{t("checksCount", { count: catalog.data.checks.length })}</span>
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
      <CheckRegistry catalog={catalog.data} quality={report} kinds={kinds.data?.kinds ?? []} />
    </Page>
  );
}

function MethodologySkeleton() {
  return (
    <Page spacing="lg" busy>
      <Skeleton width="16rem" height="2rem" />
      <div className={styles.tiles}>
        {[0, 1, 2].map((index) => (
          <div key={index} className={styles.tile}>
            <Skeleton width="60%" />
            <Skeleton shape="block" height="4.5rem" />
            <Skeleton width="40%" />
          </div>
        ))}
      </div>
      <div className={styles.checks}>
        {[0, 1, 2, 3, 4].map((index) => (
          <div key={index} className={styles.check}>
            <Skeleton width="70%" />
            <Skeleton width="90%" />
          </div>
        ))}
      </div>
    </Page>
  );
}
