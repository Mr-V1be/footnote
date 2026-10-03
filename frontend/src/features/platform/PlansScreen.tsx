"use client";

import { IconReceipt } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useApi } from "@/shared/api/ApiProvider";
import { useFormatMoney } from "@/shared/format/useFormatMoney";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { DataList, DataListSkeleton, DataRow } from "@/shared/ui/data-list/DataList";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";

import { fetchOrganizationRows, fetchPlatformPlans, platformKeys } from "./queries";

/** The plans of the service as the data defines them, and who is on each. */
export function PlansScreen() {
  const t = useTranslations("platform.plans");
  const api = useApi();
  const money = useFormatMoney();
  const planLabel = useCodeLabel("plans");
  const metricLabel = useCodeLabel("usageMetrics");
  const plans = useQuery({
    queryKey: platformKeys.plans(),
    queryFn: () => fetchPlatformPlans(api),
  });
  const rows = useQuery({
    queryKey: platformKeys.organizations(),
    queryFn: () => fetchOrganizationRows(api),
  });

  function content() {
    if (plans.isPending) return <DataListSkeleton label={t("title")} rows={3} />;
    if (plans.isError) {
      return <LoadFailure error={plans.error} onRetry={() => void plans.refetch()} />;
    }
    return (
      <DataList label={t("title")}>
        {plans.data.map((plan) => (
          <DataRow
            key={plan.code}
            leading={<IconReceipt stroke={1.75} />}
            title={planLabel(plan.code)}
            description={Object.entries(plan.limits).map(([metric, limit]) => (
              <span key={metric}>{t("limit", { metric: metricLabel(metric), limit })}</span>
            ))}
            aside={
              <>
                <span>
                  {plan.priceKopecks === 0
                    ? t("free")
                    : t("price", { price: money(plan.priceKopecks) })}
                </span>
                {rows.data ? (
                  <span>
                    {t("organizations", {
                      count: rows.data.filter((row) => row.planCode === plan.code).length,
                    })}
                  </span>
                ) : null}
              </>
            }
          />
        ))}
      </DataList>
    );
  }

  return (
    <Page>
      <PageHeader title={t("title")} />
      {content()}
    </Page>
  );
}
