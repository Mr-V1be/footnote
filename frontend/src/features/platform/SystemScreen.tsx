"use client";

import {
  IconAlertTriangle,
  IconBook2,
  IconCircleCheck,
  IconCircleX,
  IconRefresh,
} from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { LoadFailure } from "@/features/access/LoadFailure";
import { usePlatformCan } from "@/features/session/session";
import { useApi } from "@/shared/api/ApiProvider";
import type { SystemStatus } from "@/shared/api/types";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Badge, type BadgeTone } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { DataList, DataRow } from "@/shared/ui/data-list/DataList";
import { Facts } from "@/shared/ui/facts/Facts";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Section } from "@/shared/ui/section/Section";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";
import { useToast } from "@/shared/ui/toast/Toast";

import { fetchSystemStatus, platformKeys, watchCorpusNow } from "./queries";

/** The system is re-read this often while the screen is open. */
const SYSTEM_POLL_MS = 15_000;
const OUTCOME_TONES: Record<SystemStatus["editionChecks"][number]["outcome"], BadgeTone> = {
  unchanged: "neutral",
  new_edition: "important",
  failed: "critical",
};

/** The state of the stand: its services, the model, the corpus and its watch. */
export function SystemScreen() {
  const t = useTranslations("platform.system");
  const api = useApi();
  const toast = useToast();
  const format = useFormatter();
  const formatDate = useFormatDate();
  const errorText = useErrorText();
  const healthLabel = useCodeLabel("healthChecks");
  const queryClient = useQueryClient();
  const canWatch = usePlatformCan("platform.system.read");
  const system = useQuery({
    queryKey: platformKeys.system(),
    queryFn: () => fetchSystemStatus(api),
    refetchInterval: SYSTEM_POLL_MS,
  });
  const watch = useMutation({
    mutationFn: () => watchCorpusNow(api),
    onSuccess: () => {
      toast({ tone: "info", title: t("watchQueued") });
      window.setTimeout(
        () => void queryClient.invalidateQueries({ queryKey: platformKeys.system() }),
        SYSTEM_POLL_MS / 3,
      );
    },
    onError: (error) =>
      toast({ tone: "critical", title: t("watchFailed"), description: errorText(error) }),
  });

  if (system.isPending) {
    return (
      <Page busy>
        <Skeleton width="14rem" height="2rem" />
        <Skeleton shape="block" height="8rem" />
        <Skeleton shape="block" height="10rem" />
      </Page>
    );
  }
  if (system.isError) {
    return (
      <Page>
        <PageHeader title={t("title")} />
        <LoadFailure error={system.error} onRetry={() => void system.refetch()} />
      </Page>
    );
  }
  const data = system.data;
  const healthy = data.health.every((item) => item.ok);
  const actTitles = new Map(data.acts.map((act) => [act.code, act.title]));
  const moment = (iso: string) =>
    format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short" });

  return (
    <Page spacing="lg">
      <PageHeader
        title={t("title")}
        meta={
          <Badge tone={healthy ? "success" : "critical"} dot>
            {healthy ? t("healthy") : t("degraded")}
          </Badge>
        }
      />
      <Section title={t("services")}>
        <DataList label={t("services")}>
          {data.health.map((item) => (
            <DataRow
              key={item.name}
              leading={item.ok ? <IconCircleCheck stroke={1.75} /> : <IconCircleX stroke={1.75} />}
              title={healthLabel(item.name)}
              aside={
                <Badge tone={item.ok ? "success" : "critical"}>
                  {item.ok ? t("ok") : t("down")}
                </Badge>
              }
            />
          ))}
        </DataList>
      </Section>
      <Section title={t("runtime")}>
        <Facts
          columns={2}
          items={[
            {
              term: t("languageModel"),
              value: data.modelConfigured ? (data.languageModel ?? "—") : t("notConnected"),
            },
            {
              term: t("embeddingModel"),
              value: data.embeddingModel ?? t("notConnected"),
            },
            { term: t("outbox"), value: t("outboxCount", { count: data.outboxPending }) },
            {
              term: t("nextWatch"),
              value: data.nextCorpusWatch ? moment(data.nextCorpusWatch) : t("notScheduled"),
            },
          ]}
        />
      </Section>
      <Section title={t("corpus")}>
        <DataList label={t("corpus")}>
          {data.acts.map((act) => (
            <DataRow
              key={act.code}
              leading={<IconBook2 stroke={1.75} />}
              title={act.title}
              description={
                <>
                  {act.revision ? <span>{t("revision", { revision: act.revision })}</span> : null}
                  {act.activatedAt ? (
                    <span>{t("activated", { date: formatDate(act.activatedAt) })}</span>
                  ) : null}
                </>
              }
              aside={
                <Badge tone={act.indexed ? "success" : "important"}>
                  {act.indexed ? t("indexed") : t("notIndexed")}
                </Badge>
              }
            />
          ))}
        </DataList>
      </Section>
      <Section
        title={t("watch")}
        actions={
          canWatch ? (
            <Button
              variant="secondary"
              icon={<IconRefresh stroke={1.75} />}
              loading={watch.isPending}
              onClick={() => watch.mutate()}
            >
              {t("watchNow")}
            </Button>
          ) : null
        }
      >
        {data.editionChecks.length === 0 ? (
          <StatePanel icon={<IconBook2 stroke={1.75} />} title={t("noChecks")} />
        ) : (
          <DataList label={t("watch")}>
            {data.editionChecks.map((check) => (
              <DataRow
                key={`${check.actCode}-${check.checkedAt}`}
                leading={
                  check.outcome === "failed" ? (
                    <IconAlertTriangle stroke={1.75} />
                  ) : (
                    <IconBook2 stroke={1.75} />
                  )
                }
                title={t(`outcome.${check.outcome}`)}
                description={
                  <>
                    {check.revision ? (
                      <span>{t("revision", { revision: check.revision })}</span>
                    ) : null}
                    {check.error ? <span>{check.error}</span> : null}
                  </>
                }
                aside={
                  <>
                    <Badge tone={OUTCOME_TONES[check.outcome]}>
                      {actTitles.get(check.actCode) ?? check.actCode}
                    </Badge>
                    <time dateTime={check.checkedAt}>{moment(check.checkedAt)}</time>
                  </>
                }
              />
            ))}
          </DataList>
        )}
      </Section>
    </Page>
  );
}
