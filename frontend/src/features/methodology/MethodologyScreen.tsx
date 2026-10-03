"use client";

import { IconAlertTriangle } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { checkKeys, fetchCheckCatalog, fetchQuality } from "@/features/checks/queries";
import { fetchCatalog, queryKeys } from "@/features/documents/queries";
import { useApi } from "@/shared/api/ApiProvider";
import { Button } from "@/shared/ui/button/Button";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./methodology.module.css";
import { MethodologyView } from "./MethodologyView";

/** What the product checks, against which norms, and how well it does on the reference set. */
export function MethodologyScreen() {
  const t = useTranslations("methodology");
  const tc = useTranslations("common");
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

  return (
    <Page spacing="lg">
      <MethodologyView
        catalog={catalog.data}
        quality={quality.data}
        kinds={kinds.data?.kinds ?? []}
      />
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
