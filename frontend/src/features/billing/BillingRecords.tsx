"use client";

import { IconCreditCard, IconFileInvoice, IconReceipt2 } from "@tabler/icons-react";
import { useFormatter, useTranslations } from "next-intl";

import type { Billing, Invoice, LedgerEntry } from "@/shared/api/types";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { useFormatMoney } from "@/shared/format/useFormatMoney";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Badge, type BadgeTone } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { DataList, DataRow } from "@/shared/ui/data-list/DataList";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

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
export function LedgerList({ billing }: { billing: Billing }) {
  const t = useTranslations("billing");
  const formatDate = useFormatDate();
  const metricLabel = useCodeLabel("usageMetrics");
  if (billing.ledger.length === 0) {
    return <StatePanel icon={<IconReceipt2 stroke={1.75} />} title={t("noLedger")} />;
  }
  return (
    <DataList label={t("ledger")}>
      {billing.ledger.map((entry: LedgerEntry) => (
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
  );
}
