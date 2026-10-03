"use client";

import { IconCircleCheck, IconCreditCardOff } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useOrganizationAlias } from "@/features/organization/hooks";
import { useCan } from "@/features/session/membership";
import { useApi } from "@/shared/api/ApiProvider";
import { Notice } from "@/shared/ui/notice/Notice";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Section } from "@/shared/ui/section/Section";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";

import { InvoiceList, LedgerList } from "./BillingRecords";
import { PlanList } from "./PlanList";
import { PlanOverview } from "./PlanOverview";
import { billingKeys, fetchBilling } from "./queries";

/** After a payment the provider's notification is awaited this often. */
const AFTER_PAYMENT_POLL_MS = 2000;
const DAY_MS = 24 * 60 * 60 * 1000;

/** The organization's plan, this month's usage, plans to move to, invoices. */
export function BillingScreen() {
  const t = useTranslations("billing");
  const format = useFormatter();
  const api = useApi();
  const organization = useOrganizationAlias();
  const canManage = useCan("billing.manage");
  const payment = useSearchParams().get("payment");
  const billing = useQuery({
    queryKey: billingKeys.overview(organization),
    queryFn: () => fetchBilling(api, organization),
    // A paid invoice changes the plan when the provider confirms it.
    refetchInterval: (query) =>
      payment === "succeeded" && query.state.data?.invoices.some((item) => item.status === "open")
        ? AFTER_PAYMENT_POLL_MS
        : false,
  });

  if (billing.isPending) {
    return (
      <Page width="narrow" busy>
        <Skeleton width="18rem" height="2rem" />
        <Skeleton shape="block" height="14rem" />
        <Skeleton shape="block" height="12rem" />
      </Page>
    );
  }
  if (billing.isError) {
    return (
      <Page width="narrow">
        <PageHeader title={t("title")} />
        <LoadFailure error={billing.error} onRetry={() => void billing.refetch()} />
      </Page>
    );
  }
  const data = billing.data;
  const awaiting = data.invoices.some((item) => item.status === "open");
  // The period ends where the next one starts: its last day is the day before.
  const lastDay = new Date(new Date(data.periodEnd).getTime() - DAY_MS);
  const period = format.dateTimeRange(new Date(data.periodStart), lastDay, {
    day: "numeric",
    month: "long",
  });

  return (
    <Page width="narrow" spacing="lg">
      <PageHeader title={t("title")} meta={<span>{t("period", { period })}</span>} />
      {payment === "succeeded" ? (
        <Notice icon={<IconCircleCheck stroke={1.75} />} tone="success" role="status">
          {awaiting ? t("paymentConfirming") : t("paymentDone")}
        </Notice>
      ) : null}
      {payment === "declined" ? (
        <Notice icon={<IconCreditCardOff stroke={1.75} />} tone="warning" role="status">
          {t("paymentDeclined")}
        </Notice>
      ) : null}
      <PlanOverview billing={data} />
      <Section title={t("plans")}>
        <PlanList organization={organization} billing={data} canManage={canManage} />
      </Section>
      <Section title={t("invoices")}>
        <InvoiceList billing={data} canPay={canManage} />
      </Section>
      <Section title={t("ledger")}>
        <LedgerList billing={data} />
      </Section>
    </Page>
  );
}
