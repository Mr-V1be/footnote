"use client";

import { IconCreditCard, IconFileInvoice, IconReceipt2 } from "@tabler/icons-react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useApi } from "@/shared/api/ApiProvider";

import type { Billing, Invoice, LedgerEntry } from "@/shared/api/types";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { useFormatMoney } from "@/shared/format/useFormatMoney";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Badge, type BadgeTone } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { DataList, DataListSkeleton, DataRow } from "@/shared/ui/data-list/DataList";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import { billingKeys, fetchLedgerPage } from "./queries";

const INVOICE_TONES: Record<Invoice["status"], BadgeTone> = {
  open: "important",
  paid: "success",
  void: "neutral",
};

/** Invoices of the organization, the open one payable from its row. */
export function InvoiceList({ billing, canPay }: { billing: Billing; canPay: boolean }) {
  const t = useTranslations("billing");
  const format = useFormatter();
  const money = useFormatMoney();
  const planLabel = useCodeLabel("plans");
  if (billing.invoices.length === 0) {
    return <StatePanel icon={<IconFileInvoice stroke={1.75} />} title={t("noInvoices")} />;
  }
  const date = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium" });
  return (
    <DataList label={t("invoices")}>
      {billing.invoices.map((invoice) => (
        <DataRow
          key={invoice.id}
          tone={invoice.status === "void" ? "muted" : "default"}
          leading={<IconFileInvoice stroke={1.75} />}
          title={t("invoiceTitle", { number: invoice.number })}
          description={
            <>
              <span>{planLabel(invoice.planCode)}</span>
              <span>
                {invoice.paidAt
                  ? t("paidAt", { date: date(invoice.paidAt) })
                  : t("issuedAt", { date: date(invoice.issuedAt) })}
              </span>
            </>
          }
          aside={
            <>
              <Badge tone={INVOICE_TONES[invoice.status]}>
                {t(`invoiceStatus.${invoice.status}`)}
              </Badge>
              <span>{money(invoice.amountKopecks, billing.currency)}</span>
            </>
          }
          actions={
            canPay && invoice.status === "open" && invoice.paymentUrl ? (
              <Button asChild size="sm" variant="primary" icon={<IconCreditCard stroke={1.75} />}>
                <a href={invoice.paymentUrl}>{t("pay")}</a>
              </Button>
            ) : undefined
          }
        />
      ))}
    </DataList>
  );
}

/** What this month's usage was charged for, each entry with its reason. */
export function LedgerList({ organization }: { organization: string }) {
  const t = useTranslations("billing");
  const api = useApi();
  const formatDate = useFormatDate();
  const metricLabel = useCodeLabel("usageMetrics");
  const ledger = useInfiniteQuery({
    queryKey: billingKeys.ledger(organization),
    queryFn: ({ pageParam }) => fetchLedgerPage(api, organization, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor,
  });
  if (ledger.isPending) return <DataListSkeleton label={t("ledger")} rows={3} />;
  if (ledger.isError) {
    return <LoadFailure error={ledger.error} onRetry={() => void ledger.refetch()} />;
  }
  const entries = ledger.data.pages.flatMap((page) => page.items);
  if (entries.length === 0) {
    return <StatePanel icon={<IconReceipt2 stroke={1.75} />} title={t("noLedger")} />;
  }
  return (
    <>
      <DataList label={t("ledger")}>
        {entries.map((entry: LedgerEntry) => (
          <DataRow
            key={entry.id}
            title={t(`reasons.${entry.reason}`)}
            description={<time dateTime={entry.createdAt}>{formatDate(entry.createdAt)}</time>}
            aside={
              <span>
                {metricLabel(entry.metric)}: {t("quantity", { count: entry.quantity })}
              </span>
            }
          />
        ))}
      </DataList>
      {ledger.hasNextPage ? (
        <Button
          variant="secondary"
          loading={ledger.isFetchingNextPage}
          onClick={() => void ledger.fetchNextPage()}
        >
          {t("loadMore")}
        </Button>
      ) : null}
    </>
  );
}
