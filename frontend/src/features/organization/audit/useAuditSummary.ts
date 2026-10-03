"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";

import type { AuditEvent } from "@/shared/api/types";
import { useFormatMoney } from "@/shared/format/useFormatMoney";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";

type Labels = (code: string) => string;

function listOf(value: unknown, label: Labels): string {
  return String(value ?? "")
    .split(",")
    .filter(Boolean)
    .map(label)
    .join(", ");
}

/** What an event changed, in one line: roles, versions, plans, amounts. */
export function useAuditSummary(): (event: AuditEvent) => string | null {
  const t = useTranslations("audit.summary");
  const review = useTranslations("checks.review");
  const role = useCodeLabel("roles");
  const plan = useCodeLabel("plans");
  const scope = useCodeLabel("apiScopes");
  const webhookEvent = useCodeLabel("webhookEvents");
  const money = useFormatMoney();
  const reviewLabel = useCallback(
    (code: string) => (review.has(code as "open") ? review(code as "open") : code),
    [review],
  );
  return useCallback(
    (event: AuditEvent) => {
      const details = event.details;
      const text = (key: string) => String(details[key] ?? "");
      switch (event.action) {
        case "document.uploaded":
          return text("file");
        case "document.version_added":
          return t("versionFile", { number: text("version"), file: text("file") });
        case "document.autofixed":
          return t("autofixed", {
            from: text("from_version"),
            number: text("version"),
            changes: Number(details.changes ?? 0),
          });
        case "check.requested":
          return t("version", { number: text("version") });
        case "finding.reviewed":
          return t("change", { from: reviewLabel(text("from")), to: reviewLabel(text("to")) });
        case "member.invited":
          return role(text("role"));
        case "member.role_changed":
          return t("change", { from: listOf(details.from, role), to: role(text("to")) });
        case "workspace.created":
          return details.restricted ? t("restricted") : t("open");
        case "workspace.member_set":
          return t("memberRole", { member: text("member"), role: role(text("role")) });
        case "workspace.member_removed":
          return text("member");
        case "api_key.created":
          return listOf(details.scopes, scope);
        case "webhook.created":
          return listOf(details.events, webhookEvent);
        case "webhook.updated":
          if (details.secret) return t("secretRotated");
          return details.active === false ? t("paused") : t("active");
        case "billing.plan_change_requested":
          return details.from_month
            ? t("planNextMonth", { from: plan(text("from")), to: plan(text("to")) })
            : t("planInvoice", {
                to: plan(text("to")),
                amount: money(Number(details.amount_kopecks ?? 0)),
              });
        case "billing.invoice_paid":
          return money(Number(details.amount_kopecks ?? 0));
        case "billing.plan_changed":
          return t("change", { from: plan(text("from")), to: plan(text("to")) });
        case "member.removed":
        case "workspace.updated":
        case "workspace.deleted":
        case "api_key.revoked":
        case "webhook.deleted":
          return null;
      }
    },
    [t, reviewLabel, role, plan, scope, webhookEvent, money],
  );
}
