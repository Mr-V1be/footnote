"use client";

import { IconBuilding } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { usePlatformCan } from "@/features/session/session";
import { useApi } from "@/shared/api/ApiProvider";
import type { OrganizationRow, Plan } from "@/shared/api/types";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog/ConfirmDialog";
import { DataList, DataListSkeleton, DataRow } from "@/shared/ui/data-list/DataList";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Select } from "@/shared/ui/select/Select";
import { useToast } from "@/shared/ui/toast/Toast";

import styles from "./platform.module.css";
import { assignPlan, fetchOrganizationRows, fetchPlatformPlans, platformKeys } from "./queries";

/** The metrics an organization's row shows against its plan. */
const ROW_METRICS = ["pages", "checks"] as const;

interface Assignment {
  organization: OrganizationRow;
  plan: string;
}

/** Every organization of the service with its plan and this month's usage. */
export function OrganizationsScreen() {
  const t = useTranslations("platform");
  const api = useApi();
  const [assigning, setAssigning] = useState<Assignment | null>(null);
  const rows = useQuery({
    queryKey: platformKeys.organizations(),
    queryFn: () => fetchOrganizationRows(api),
  });
  const plans = useQuery({
    queryKey: platformKeys.plans(),
    queryFn: () => fetchPlatformPlans(api),
  });

  function content() {
    if (rows.isPending || plans.isPending) {
      return <DataListSkeleton label={t("organizations.title")} rows={4} />;
    }
    if (rows.isError || plans.isError) {
      return (
        <LoadFailure
          error={rows.error ?? plans.error}
          onRetry={() => void Promise.all([rows.refetch(), plans.refetch()])}
        />
      );
    }
    return (
      <DataList label={t("organizations.title")}>
        {rows.data.map((row) => (
          <OrganizationItem
            key={row.id}
            row={row}
            plans={plans.data}
            onAssign={(plan) => setAssigning({ organization: row, plan })}
          />
        ))}
      </DataList>
    );
  }

  return (
    <Page>
      <PageHeader
        title={t("organizations.title")}
        meta={
          rows.data ? <span>{t("organizations.count", { count: rows.data.length })}</span> : null
        }
      />
      {content()}
      <AssignPlanDialog assignment={assigning} onClose={() => setAssigning(null)} />
    </Page>
  );
}

function OrganizationItem({
  row,
  plans,
  onAssign,
}: {
  row: OrganizationRow;
  plans: readonly Plan[];
  onAssign: (plan: string) => void;
}) {
  const t = useTranslations("platform.organizations");
  const formatDate = useFormatDate();
  const planLabel = useCodeLabel("plans");
  const metricLabel = useCodeLabel("usageMetrics");
  const canAssign = usePlatformCan("platform.plans.manage");
  const plan = plans.find((item) => item.code === row.planCode);
  return (
    <DataRow
      leading={<IconBuilding stroke={1.75} />}
      title={row.name}
      description={
        <>
          <span>{row.alias}</span>
          <span>{t("since", { date: formatDate(row.createdAt) })}</span>
          {row.members !== null ? <span>{t("members", { count: row.members })}</span> : null}
          {ROW_METRICS.map((metric) => (
            <span key={metric}>
              {t("usage", {
                metric: metricLabel(metric),
                used: row.used[metric] ?? 0,
                limit: plan?.limits[metric] ?? 0,
              })}
            </span>
          ))}
        </>
      }
      aside={
        canAssign ? (
          <div className={styles.plan}>
            <Select
              block
              size="sm"
              label={t("planOf", { name: row.name })}
              value={row.planCode}
              onValueChange={(code) => code !== row.planCode && onAssign(code)}
              options={plans.map((item) => ({ value: item.code, label: planLabel(item.code) }))}
            />
          </div>
        ) : (
          <span>{planLabel(row.planCode)}</span>
        )
      }
    />
  );
}

function AssignPlanDialog({
  assignment,
  onClose,
}: {
  assignment: Assignment | null;
  onClose: () => void;
}) {
  const t = useTranslations("platform.organizations");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const planLabel = useCodeLabel("plans");
  const queryClient = useQueryClient();
  const assign = useMutation({
    mutationFn: (target: Assignment) => assignPlan(api, target.organization.id, target.plan),
    onSuccess: async (_result, target) => {
      await queryClient.invalidateQueries({ queryKey: platformKeys.organizations() });
      toast({
        tone: "success",
        title: t("assigned", { name: target.organization.name, plan: planLabel(target.plan) }),
      });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open={assignment !== null}
      onOpenChange={(open) => {
        if (!open) {
          assign.reset();
          onClose();
        }
      }}
      title={t("assignTitle", {
        name: assignment?.organization.name ?? "",
        plan: planLabel(assignment?.plan ?? ""),
      })}
      consequences={<p>{t("assignConsequence")}</p>}
      confirmLabel={t("assignConfirm")}
      cancelLabel={tc("cancel")}
      closeLabel={tc("close")}
      pending={assign.isPending}
      error={assign.isError ? errorText(assign.error) : null}
      onConfirm={() => assignment && assign.mutate(assignment)}
    />
  );
}
