"use client";

import { IconPlus, IconWebhook, IconWebhookOff } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useOrganizationAlias } from "@/features/organization/hooks";
import { useApi } from "@/shared/api/ApiProvider";
import type { Webhook } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Badge } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { DataList, DataListSkeleton, DataRow, DataRowLink } from "@/shared/ui/data-list/DataList";
import { Page } from "@/shared/ui/page/Page";
import { PageAction } from "@/shared/ui/page-action/PageAction";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import { fetchWebhooks, integrationKeys } from "../queries";
import { RevealOnceDialog } from "../RevealOnceDialog";
import { WebhookDialog } from "./WebhookDialog";

/** Addresses the organization's events are sent to, signed. */
export function WebhooksScreen() {
  const t = useTranslations("webhooks");
  const api = useApi();
  const router = useRouter();
  const organization = useOrganizationAlias();
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<{ id: string; secret: string } | null>(null);
  const webhooks = useQuery({
    queryKey: integrationKeys.webhooks(organization),
    queryFn: () => fetchWebhooks(api, organization),
  });

  function content() {
    if (webhooks.isPending) return <DataListSkeleton label={t("title")} rows={2} />;
    if (webhooks.isError) {
      return <LoadFailure error={webhooks.error} onRetry={() => void webhooks.refetch()} />;
    }
    if (webhooks.data.length === 0) {
      return (
        <StatePanel
          icon={<IconWebhook stroke={1.75} />}
          title={t("emptyTitle")}
          description={t("emptyDescription")}
          action={
            <Button
              variant="primary"
              icon={<IconPlus stroke={1.75} />}
              onClick={() => setCreating(true)}
            >
              {t("create")}
            </Button>
          }
        />
      );
    }
    return (
      <DataList label={t("title")}>
        {webhooks.data.map((webhook) => (
          <WebhookRow key={webhook.id} webhook={webhook} organization={organization} />
        ))}
      </DataList>
    );
  }

  return (
    <Page width="narrow">
      <PageHeader
        title={t("title")}
        actions={
          webhooks.data?.length ? (
            <PageAction
              icon={<IconPlus stroke={1.75} />}
              label={t("create")}
              onClick={() => setCreating(true)}
            />
          ) : undefined
        }
      />
      {content()}
      <WebhookDialog
        organization={organization}
        open={creating}
        onOpenChange={setCreating}
        onCreated={(result) => setCreated({ id: result.endpoint.id, secret: result.secret })}
      />
      <RevealOnceDialog
        secret={created?.secret ?? null}
        title={t("secretTitle")}
        label={t("secret")}
        onClose={() => {
          if (created) router.push(`/o/${organization}/settings/webhooks/${created.id}`);
          setCreated(null);
        }}
      />
    </Page>
  );
}

function WebhookRow({ webhook, organization }: { webhook: Webhook; organization: string }) {
  const t = useTranslations("webhooks");
  const eventLabel = useCodeLabel("webhookEvents");
  return (
    <DataRow
      tone={webhook.active ? "default" : "muted"}
      leading={webhook.active ? <IconWebhook stroke={1.75} /> : <IconWebhookOff stroke={1.75} />}
      title={
        <DataRowLink href={`/o/${organization}/settings/webhooks/${webhook.id}`}>
          {webhook.description || webhook.url}
        </DataRowLink>
      }
      description={
        <>
          {webhook.description ? <span>{webhook.url}</span> : null}
          <span>{webhook.events.map(eventLabel).join(", ")}</span>
        </>
      }
      aside={
        <Badge tone={webhook.active ? "success" : "neutral"} dot>
          {webhook.active ? t("activeBadge") : t("pausedBadge")}
        </Badge>
      }
    />
  );
}
