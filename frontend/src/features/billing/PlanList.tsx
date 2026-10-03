"use client";

import {
  IconAlertTriangle,
  IconArrowDown,
  IconArrowUp,
  IconCircleCheck,
} from "@tabler/icons-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { useApi } from "@/shared/api/ApiProvider";
import type { Billing, Plan } from "@/shared/api/types";
import { useFormatMoney } from "@/shared/format/useFormatMoney";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Badge } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { Dialog, DialogClose, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Form, FormError } from "@/shared/ui/form/Form";
import { Notice } from "@/shared/ui/notice/Notice";
import { useToast } from "@/shared/ui/toast/Toast";

import styles from "./billing.module.css";
import { billingKeys, changePlan } from "./queries";

/** The plans side by side; the owner moves to another one from here. */
export function PlanList({
  organization,
  billing,
  canManage,
}: {
  organization: string;
  billing: Billing;
  canManage: boolean;
}) {
  const [target, setTarget] = useState<Plan | null>(null);
  return (
    <>
      <div className={styles.plans}>
        {billing.plans.map((plan) => (
          <PlanCard
            key={plan.code}
            plan={plan}
            billing={billing}
            canManage={canManage}
            onChoose={() => setTarget(plan)}
          />
        ))}
      </div>
      <PlanChangeDialog
        organization={organization}
        billing={billing}
        target={target}
        onClose={() => setTarget(null)}
      />
    </>
  );
}

function PlanCard({
  plan,
  billing,
  canManage,
  onChoose,
}: {
  plan: Plan;
  billing: Billing;
  canManage: boolean;
  onChoose: () => void;
}) {
  const t = useTranslations("billing");
  const money = useFormatMoney();
  const planLabel = useCodeLabel("plans");
  const metricLabel = useCodeLabel("usageMetrics");
  const current = plan.code === billing.plan.code;
  const pending = plan.code === billing.pendingPlan?.code;
  const upgrade = plan.rank > billing.plan.rank;
  return (
    <article className={`${styles.plan} ${current ? styles.current : ""}`}>
      <div className={styles.planHead}>
        <h3 className={styles.planTitle}>{planLabel(plan.code)}</h3>
        {current ? (
          <Badge tone="ink" dot>
            {t("currentBadge")}
          </Badge>
        ) : pending ? (
          <Badge tone="important">{t("pendingBadge")}</Badge>
        ) : null}
      </div>
      <p className={styles.planPrice}>
        {plan.priceKopecks === 0 ? t("free") : money(plan.priceKopecks, billing.currency)}
        {plan.priceKopecks === 0 ? null : <span className={styles.perMonth}> {t("month")}</span>}
      </p>
      <ul className={styles.limits}>
        {billing.usage.map(({ metric }) => (
          <li key={metric} className={styles.limit}>
            <span>{metricLabel(metric)}</span>
            <span className={styles.limitValue}>{plan.limits[metric] ?? "—"}</span>
          </li>
        ))}
      </ul>
      {canManage && !current && !pending ? (
        <Button
          variant={upgrade ? "primary" : "secondary"}
          icon={upgrade ? <IconArrowUp stroke={1.75} /> : <IconArrowDown stroke={1.75} />}
          onClick={onChoose}
          block
        >
          {upgrade ? t("upgrade") : t("downgrade")}
        </Button>
      ) : null}
    </article>
  );
}

function PlanChangeDialog({
  organization,
  billing,
  target,
  onClose,
}: {
  organization: string;
  billing: Billing;
  target: Plan | null;
  onClose: () => void;
}) {
  const t = useTranslations("billing");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const format = useFormatter();
  const money = useFormatMoney();
  const errorText = useErrorText();
  const planLabel = useCodeLabel("plans");
  const queryClient = useQueryClient();
  const upgrade = target ? target.rank > billing.plan.rank : false;
  const nextMonth = format.dateTime(new Date(billing.periodEnd), { day: "numeric", month: "long" });

  const change = useMutation({
    mutationFn: (plan: Plan) => changePlan(api, organization, plan.code),
    onSuccess: async (result, plan) => {
      if (result.change === "awaiting_payment" && result.invoice?.paymentUrl) {
        // The payment provider's page; it returns to this screen afterwards.
        window.location.assign(result.invoice.paymentUrl);
        return;
      }
      await queryClient.invalidateQueries({ queryKey: billingKeys.overview(organization) });
      toast({
        tone: "success",
        title: t("scheduled", { plan: planLabel(plan.code), date: nextMonth }),
      });
      onClose();
    },
  });
  // Limits that would be lower than what is already used this month.
  const tight = target
    ? billing.usage.filter((usage) => (usage.used ?? 0) > (target.limits[usage.metric] ?? 0))
    : [];

  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) {
          change.reset();
          onClose();
        }
      }}
    >
      {target ? (
        <DialogContent
          title={t("changeTitle", { plan: planLabel(target.code) })}
          closeLabel={tc("close")}
          footer={
            <>
              <DialogClose asChild>
                <Button variant="secondary">{tc("cancel")}</Button>
              </DialogClose>
              <Button
                variant="primary"
                icon={<IconCircleCheck stroke={1.75} />}
                loading={change.isPending || change.isSuccess}
                onClick={() => change.mutate(target)}
              >
                {upgrade ? t("toPayment") : t("confirmDowngrade")}
              </Button>
            </>
          }
        >
          <Form>
            <p>
              {upgrade
                ? t("upgradeConsequence", {
                    price: money(target.priceKopecks, billing.currency),
                  })
                : t("downgradeConsequence", { date: nextMonth })}
            </p>
            {!upgrade && tight.length > 0 ? (
              <Notice icon={<IconAlertTriangle stroke={1.75} />} tone="warning">
                {t("downgradeTight", { count: tight.length })}
              </Notice>
            ) : null}
            {change.isError ? <FormError>{errorText(change.error)}</FormError> : null}
          </Form>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}
