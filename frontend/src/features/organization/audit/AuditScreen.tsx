"use client";

import {
  IconActivity,
  IconCalendar,
  IconCategory,
  IconChecklist,
  IconDownload,
  IconFileText,
  IconFolder,
  IconHistory,
  IconKey,
  IconMessageCheck,
  IconReceipt,
  IconUser,
  IconUserCircle,
  IconWebhook,
  type Icon,
} from "@tabler/icons-react";
import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { useFormatter, useNow, useTranslations } from "next-intl";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useApi } from "@/shared/api/ApiProvider";
import type { ActorKind, AuditEvent } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Button } from "@/shared/ui/button/Button";
import { DataList, DataListSkeleton, DataRow } from "@/shared/ui/data-list/DataList";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Select } from "@/shared/ui/select/Select";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";
import { Toolbar } from "@/shared/ui/toolbar/Toolbar";

import { useAdministrationCatalog, useOrganizationAlias } from "../hooks";
import { adminKeys, auditExportUrl, fetchAuditPage } from "../queries";
import { AUDIT_PERIODS, useAuditFilters } from "./useAuditFilters";
import { useAuditSummary } from "./useAuditSummary";

const ALL = "__all";
const CATEGORY_ICONS: Record<string, Icon> = {
  document: IconFileText,
  check: IconChecklist,
  finding: IconMessageCheck,
  member: IconUser,
  workspace: IconFolder,
  api_key: IconKey,
  webhook: IconWebhook,
  billing: IconReceipt,
};

/** Who did what and when: documents, checks, decisions, people, keys, plans. */
export function AuditScreen() {
  const t = useTranslations("audit");
  const api = useApi();
  const organization = useOrganizationAlias();
  const catalog = useAdministrationCatalog();
  const categoryLabel = useCodeLabel("auditCategories");
  const actorLabel = useCodeLabel("actorKinds");
  const { filters, set } = useAuditFilters();
  // The server's moment, the same in both renders: pages and export agree.
  const now = useNow();

  const log = useInfiniteQuery({
    queryKey: adminKeys.audit(organization, filters),
    queryFn: ({ pageParam }) => fetchAuditPage(api, organization, filters, now, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor,
    placeholderData: keepPreviousData,
  });
  const items = log.data?.pages.flatMap((page) => page.items) ?? [];
  const filtered = filters.category !== null || filters.actorKind !== null;

  function content() {
    if (log.isPending) return <DataListSkeleton label={t("title")} rows={8} />;
    if (log.isError) return <LoadFailure error={log.error} onRetry={() => void log.refetch()} />;
    if (items.length === 0) {
      return (
        <StatePanel
          icon={<IconHistory stroke={1.75} />}
          title={filtered ? t("noMatchesTitle") : t("emptyTitle")}
          description={filtered ? t("noMatchesDescription") : t("emptyDescription")}
          action={
            filtered ? (
              <Button variant="secondary" onClick={() => set({ category: null, actorKind: null })}>
                {t("resetFilters")}
              </Button>
            ) : undefined
          }
        />
      );
    }
    return (
      <>
        <DataList label={t("title")} busy={log.isPlaceholderData}>
          {items.map((event) => (
            <AuditRow key={event.id} event={event} />
          ))}
        </DataList>
        {log.hasNextPage ? (
          <Button
            variant="secondary"
            loading={log.isFetchingNextPage}
            onClick={() => void log.fetchNextPage()}
          >
            {t("loadMore")}
          </Button>
        ) : null}
      </>
    );
  }

  return (
    <Page>
      <PageHeader
        title={t("title")}
        actions={
          <Button asChild variant="secondary" icon={<IconDownload stroke={1.75} />}>
            <a href={auditExportUrl(organization, filters, now)} download>
              {t("export")}
            </a>
          </Button>
        }
      />
      <Toolbar label={t("filters")}>
        <Select
          label={t("category")}
          icon={<IconCategory stroke={1.75} />}
          value={filters.category ?? ALL}
          onValueChange={(value) => set({ category: value === ALL ? null : value })}
          options={[
            { value: ALL, label: t("allCategories") },
            ...(catalog.data?.auditCategories ?? []).map((code) => ({
              value: code,
              label: categoryLabel(code),
            })),
          ]}
        />
        <Select
          label={t("actor")}
          icon={<IconUserCircle stroke={1.75} />}
          value={filters.actorKind ?? ALL}
          onValueChange={(value) => set({ actorKind: value === ALL ? null : (value as ActorKind) })}
          options={[
            { value: ALL, label: t("allActors") },
            ...(catalog.data?.actorKinds ?? []).map((code) => ({
              value: code,
              label: actorLabel(code),
            })),
          ]}
        />
        <Select
          label={t("period")}
          icon={<IconCalendar stroke={1.75} />}
          value={filters.days === null ? "all" : String(filters.days)}
          onValueChange={(value) => set({ days: value === "all" ? null : Number(value) })}
          options={AUDIT_PERIODS.map((days) =>
            days === null
              ? { value: "all", label: t("allTime") }
              : { value: String(days), label: t("lastDays", { count: days }) },
          )}
        />
      </Toolbar>
      {content()}
    </Page>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  const t = useTranslations("audit");
  const format = useFormatter();
  const now = useNow();
  const actionLabel = useCodeLabel("auditActions");
  const actorLabel = useCodeLabel("actorKinds");
  const summary = useAuditSummary()(event);
  const Glyph = CATEGORY_ICONS[event.category] ?? IconActivity;
  const date = new Date(event.occurredAt);
  const sameYear = date.getFullYear() === now.getFullYear();
  return (
    <DataRow
      leading={<Glyph stroke={1.75} />}
      title={actionLabel(event.action)}
      description={
        <>
          {/* A plan's label is its code; the summary names the plans. */}
          {event.target.label && event.target.type !== "plan" ? (
            <span>{event.target.label}</span>
          ) : null}
          {summary ? <span>{summary}</span> : null}
          <span>
            {event.actor.kind === "user"
              ? event.actor.label
              : event.actor.kind === "api_key"
                ? t("actorOf", { kind: actorLabel(event.actor.kind), name: event.actor.label })
                : actorLabel(event.actor.kind)}
          </span>
        </>
      }
      aside={
        <time dateTime={event.occurredAt}>
          {format.dateTime(date, {
            day: "numeric",
            month: "short",
            ...(sameYear ? {} : { year: "numeric" }),
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
      }
    />
  );
}
