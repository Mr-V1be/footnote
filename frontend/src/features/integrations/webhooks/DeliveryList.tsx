"use client";

import {
  IconAlertTriangle,
  IconCircleCheck,
  IconClockHour4,
  IconCode,
  IconDotsVertical,
  IconRefresh,
  IconSend,
  type Icon,
} from "@tabler/icons-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { useApi } from "@/shared/api/ApiProvider";
import type { Delivery, DeliveryStatus } from "@/shared/api/types";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Badge, type BadgeTone } from "@/shared/ui/badge/Badge";
import { DataList, DataRow } from "@/shared/ui/data-list/DataList";
import { Drawer, DrawerContent } from "@/shared/ui/drawer/Drawer";
import { Facts } from "@/shared/ui/facts/Facts";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/shared/ui/menu/Menu";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { useToast } from "@/shared/ui/toast/Toast";

import { integrationKeys, retryDelivery } from "../queries";
import styles from "./webhooks.module.css";

const STATUS: Record<DeliveryStatus, { icon: Icon; tone: BadgeTone }> = {
  pending: { icon: IconSend, tone: "ink" },
  delivered: { icon: IconCircleCheck, tone: "success" },
  retrying: { icon: IconClockHour4, tone: "important" },
  failed: { icon: IconAlertTriangle, tone: "critical" },
};

/** Every attempt to deliver an event: status, answer, the next try. */
export function DeliveryList({
  organization,
  endpointId,
  deliveries,
}: {
  organization: string;
  endpointId: string;
  deliveries: readonly Delivery[];
}) {
  const t = useTranslations("webhooks");
  const [shown, setShown] = useState<Delivery | null>(null);
  return (
    <>
      <DataList label={t("deliveries")} reserveActions>
        {deliveries.map((delivery) => (
          <DeliveryRow
            key={delivery.id}
            organization={organization}
            endpointId={endpointId}
            delivery={delivery}
            onShow={() => setShown(delivery)}
          />
        ))}
      </DataList>
      <DeliveryDetails delivery={shown} onClose={() => setShown(null)} />
    </>
  );
}

function DeliveryRow({
  organization,
  endpointId,
  delivery,
  onShow,
}: {
  organization: string;
  endpointId: string;
  delivery: Delivery;
  onShow: () => void;
}) {
  const t = useTranslations("webhooks");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const formatDate = useFormatDate();
  const eventLabel = useCodeLabel("webhookEvents");
  const queryClient = useQueryClient();
  const status = STATUS[delivery.status];
  const Glyph = status.icon;
  const retry = useMutation({
    mutationFn: () => retryDelivery(api, organization, endpointId, delivery.id),
    onSuccess: (saved) => {
      queryClient.setQueryData<Delivery[]>(
        integrationKeys.deliveries(organization, endpointId),
        (current) => current?.map((item) => (item.id === saved.id ? saved : item)),
      );
      toast({ tone: "info", title: t("retryQueued") });
    },
    onError: (error) =>
      toast({ tone: "critical", title: t("retryFailed"), description: errorText(error) }),
  });
  return (
    <DataRow
      leading={<Glyph stroke={1.75} className={styles[delivery.status]} />}
      title={eventLabel(delivery.event)}
      description={
        <>
          <span>{t("attempts", { count: delivery.attempts })}</span>
          {delivery.lastStatusCode !== null ? (
            <span>{t("answer", { code: delivery.lastStatusCode })}</span>
          ) : null}
          {delivery.lastError ? <span>{delivery.lastError}</span> : null}
          {delivery.nextAttemptAt && delivery.status === "retrying" ? (
            <span>{t("nextAttempt", { date: formatDate(delivery.nextAttemptAt) })}</span>
          ) : null}
        </>
      }
      aside={
        <>
          <Badge tone={status.tone}>{t(`status.${delivery.status}`)}</Badge>
          <time dateTime={delivery.createdAt}>{formatDate(delivery.createdAt)}</time>
        </>
      }
      actions={
        <Menu>
          <MenuTrigger asChild>
            <IconButton
              label={t("deliveryActions")}
              icon={<IconDotsVertical stroke={1.75} />}
              tooltip={false}
            />
          </MenuTrigger>
          <MenuContent align="end">
            <MenuItem icon={<IconCode stroke={1.75} />} onSelect={onShow}>
              {t("showPayload")}
            </MenuItem>
            {delivery.status === "failed" || delivery.status === "delivered" ? (
              <MenuItem icon={<IconRefresh stroke={1.75} />} onSelect={() => retry.mutate()}>
                {t("redeliver")}
              </MenuItem>
            ) : null}
          </MenuContent>
        </Menu>
      }
    />
  );
}

function DeliveryDetails({
  delivery,
  onClose,
}: {
  delivery: Delivery | null;
  onClose: () => void;
}) {
  const t = useTranslations("webhooks");
  const tc = useTranslations("common");
  const format = useFormatter();
  const eventLabel = useCodeLabel("webhookEvents");
  const wide = useMediaQuery("(width >= 48rem)");
  const moment = (iso: string) =>
    format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "medium" });
  return (
    <Drawer open={delivery !== null} onOpenChange={(open) => !open && onClose()}>
      {delivery ? (
        <DrawerContent
          side={wide ? "right" : "bottom"}
          title={eventLabel(delivery.event)}
          closeLabel={tc("close")}
        >
          <div className={styles.details}>
            <Facts
              items={[
                { term: t("statusLabel"), value: t(`status.${delivery.status}`) },
                { term: t("created"), value: moment(delivery.createdAt) },
                ...(delivery.deliveredAt
                  ? [{ term: t("delivered"), value: moment(delivery.deliveredAt) }]
                  : []),
                { term: t("attemptsLabel"), value: String(delivery.attempts) },
                ...(delivery.lastStatusCode !== null
                  ? [{ term: t("answerLabel"), value: String(delivery.lastStatusCode) }]
                  : []),
                ...(delivery.lastDurationMs !== null
                  ? [{ term: t("duration"), value: t("ms", { value: delivery.lastDurationMs }) }]
                  : []),
              ]}
            />
            <pre className={styles.payload}>{JSON.stringify(delivery.payload, null, 2)}</pre>
          </div>
        </DrawerContent>
      ) : null}
    </Drawer>
  );
}
