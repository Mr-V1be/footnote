"use client";

import {
  IconDotsVertical,
  IconKey,
  IconPencil,
  IconSend,
  IconTrash,
  IconTruckDelivery,
} from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useOrganizationAlias } from "@/features/organization/hooks";
import { useApi } from "@/shared/api/ApiProvider";
import { ApiError } from "@/shared/api/errors";
import type { Delivery, Webhook } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { BackLink } from "@/shared/ui/back-link/BackLink";
import { Badge } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog/ConfirmDialog";
import { DataListSkeleton } from "@/shared/ui/data-list/DataList";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/shared/ui/menu/Menu";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Section } from "@/shared/ui/section/Section";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";
import { useToast } from "@/shared/ui/toast/Toast";

import {
  DELIVERY_POLL_MS,
  deleteWebhook,
  fetchDeliveries,
  fetchWebhooks,
  integrationKeys,
  isInFlight,
  pingWebhook,
  rotateWebhookSecret,
} from "../queries";
import { RevealOnceDialog } from "../RevealOnceDialog";
import { DeliveryList } from "./DeliveryList";
import { WebhookDialog } from "./WebhookDialog";

/** One endpoint: its settings and the log of its deliveries. */
export function WebhookScreen({ endpointId }: { endpointId: string }) {
  const t = useTranslations("webhooks");
  const api = useApi();
  const organization = useOrganizationAlias();
  const webhooks = useQuery({
    queryKey: integrationKeys.webhooks(organization),
    queryFn: () => fetchWebhooks(api, organization),
  });
  const listHref = `/o/${organization}/settings/webhooks`;

  if (webhooks.isPending) {
    return (
      <Page width="narrow" busy>
        <Skeleton width="16rem" height="2rem" />
        <DataListSkeleton label={t("deliveries")} rows={4} />
      </Page>
    );
  }
  const webhook = webhooks.data?.find((item) => item.id === endpointId);
  if (webhooks.isError || !webhook) {
    return (
      <Page width="narrow">
        <BackLink href={listHref} label={t("title")} />
        <LoadFailure
          error={webhooks.error ?? new ApiError(404, "webhook_not_found")}
          onRetry={() => void webhooks.refetch()}
        />
      </Page>
    );
  }
  return <WebhookDetails organization={organization} webhook={webhook} listHref={listHref} />;
}

function WebhookDetails({
  organization,
  webhook,
  listHref,
}: {
  organization: string;
  webhook: Webhook;
  listHref: string;
}) {
  const t = useTranslations("webhooks");
  const tc = useTranslations("common");
  const api = useApi();
  const router = useRouter();
  const toast = useToast();
  const errorText = useErrorText();
  const eventLabel = useCodeLabel("webhookEvents");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);
  const deliveriesKey = integrationKeys.deliveries(organization, webhook.id);
  const deliveries = useQuery({
    queryKey: deliveriesKey,
    queryFn: () => fetchDeliveries(api, organization, webhook.id),
    refetchInterval: (query) =>
      query.state.data?.some((delivery) => isInFlight(delivery.status)) ? DELIVERY_POLL_MS : false,
  });

  const ping = useMutation({
    mutationFn: () => pingWebhook(api, organization, webhook.id),
    onSuccess: (delivery) => {
      queryClient.setQueryData<Delivery[]>(deliveriesKey, (current) =>
        current ? [delivery, ...current] : [delivery],
      );
      toast({ tone: "info", title: t("pingQueued") });
    },
    onError: (error) =>
      toast({ tone: "critical", title: t("pingFailed"), description: errorText(error) }),
  });
  const rotate = useMutation({
    mutationFn: () => rotateWebhookSecret(api, organization, webhook.id),
    onSuccess: (result) => {
      setRotating(false);
      setSecret(result.secret);
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteWebhook(api, organization, webhook.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: integrationKeys.webhooks(organization) });
      toast({ tone: "success", title: t("deleted") });
      router.push(listHref);
    },
  });

  function content() {
    if (deliveries.isPending) return <DataListSkeleton label={t("deliveries")} rows={4} />;
    if (deliveries.isError) {
      return <LoadFailure error={deliveries.error} onRetry={() => void deliveries.refetch()} />;
    }
    if (deliveries.data.length === 0) {
      return (
        <StatePanel
          icon={<IconTruckDelivery stroke={1.75} />}
          title={t("noDeliveriesTitle")}
          description={t("noDeliveriesDescription")}
        />
      );
    }
    return (
      <DeliveryList
        organization={organization}
        endpointId={webhook.id}
        deliveries={deliveries.data}
      />
    );
  }

  return (
    <Page width="narrow">
      <PageHeader
        leading={<BackLink href={listHref} label={t("title")} />}
        title={webhook.description || webhook.url}
        meta={
          <>
            <Badge tone={webhook.active ? "success" : "neutral"} dot>
              {webhook.active ? t("activeBadge") : t("pausedBadge")}
            </Badge>
            {webhook.description ? <span>{webhook.url}</span> : null}
            <span>{webhook.events.map(eventLabel).join(", ")}</span>
          </>
        }
        actions={
          <>
            <Button
              variant="primary"
              icon={<IconSend stroke={1.75} />}
              loading={ping.isPending}
              disabled={!webhook.active}
              onClick={() => ping.mutate()}
            >
              {t("ping")}
            </Button>
            <Menu>
              <MenuTrigger asChild>
                <IconButton
                  label={t("actions")}
                  icon={<IconDotsVertical stroke={1.75} />}
                  variant="secondary"
                  tooltip={false}
                />
              </MenuTrigger>
              <MenuContent align="end">
                <MenuItem icon={<IconPencil stroke={1.75} />} onSelect={() => setEditing(true)}>
                  {t("edit")}
                </MenuItem>
                <MenuItem icon={<IconKey stroke={1.75} />} onSelect={() => setRotating(true)}>
                  {t("rotate")}
                </MenuItem>
                <MenuItem
                  icon={<IconTrash stroke={1.75} />}
                  tone="critical"
                  onSelect={() => setDeleting(true)}
                >
                  {t("delete")}
                </MenuItem>
              </MenuContent>
            </Menu>
          </>
        }
      />
      <Section title={t("deliveries")}>{content()}</Section>
      <WebhookDialog
        organization={organization}
        webhook={webhook}
        open={editing}
        onOpenChange={setEditing}
      />
      <RevealOnceDialog
        secret={secret}
        title={t("rotatedTitle")}
        label={t("secret")}
        onClose={() => setSecret(null)}
      />
      <ConfirmDialog
        open={rotating}
        onOpenChange={(open) => {
          if (!open) rotate.reset();
          setRotating(open);
        }}
        title={t("rotateTitle")}
        consequences={<p>{t("rotateConsequence")}</p>}
        confirmLabel={t("rotateConfirm")}
        cancelLabel={tc("cancel")}
        closeLabel={tc("close")}
        pending={rotate.isPending}
        error={rotate.isError ? errorText(rotate.error) : null}
        onConfirm={() => rotate.mutate()}
      />
      <ConfirmDialog
        open={deleting}
        onOpenChange={(open) => {
          if (!open) remove.reset();
          setDeleting(open);
        }}
        title={t("deleteTitle")}
        consequences={<p>{t("deleteConsequence")}</p>}
        confirmLabel={t("deleteConfirm")}
        cancelLabel={tc("cancel")}
        closeLabel={tc("close")}
        pending={remove.isPending}
        error={remove.isError ? errorText(remove.error) : null}
        onConfirm={() => remove.mutate()}
      />
    </Page>
  );
}
