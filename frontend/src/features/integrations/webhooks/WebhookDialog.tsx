"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { useAdministrationCatalog } from "@/features/organization/hooks";
import { useApi } from "@/shared/api/ApiProvider";
import type { Webhook, WebhookEvent, WebhookWithSecret } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Button } from "@/shared/ui/button/Button";
import { CheckboxGroup } from "@/shared/ui/checkbox-group/CheckboxGroup";
import { Dialog, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Field, TextInput } from "@/shared/ui/field/Field";
import { Form, FormError } from "@/shared/ui/form/Form";
import { Switch } from "@/shared/ui/switch/Switch";
import { useToast } from "@/shared/ui/toast/Toast";

import { createWebhook, integrationKeys, updateWebhook } from "../queries";

const URL_PATTERN = /^https?:\/\/[^\s/@]+(?::\d+)?(?:\/\S*)?$/;

/** A new endpoint (its secret is shown once after), or the settings of one. */
export function WebhookDialog({
  organization,
  webhook,
  open,
  onOpenChange,
  onCreated,
}: {
  organization: string;
  webhook?: Webhook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (created: WebhookWithSecret) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <WebhookForm
          organization={organization}
          webhook={webhook}
          onCancel={() => onOpenChange(false)}
          onSaved={(created) => {
            onOpenChange(false);
            if (created) onCreated?.(created);
          }}
        />
      ) : null}
    </Dialog>
  );
}

function WebhookForm({
  organization,
  webhook,
  onCancel,
  onSaved,
}: {
  organization: string;
  webhook?: Webhook;
  onCancel: () => void;
  onSaved: (created: WebhookWithSecret | null) => void;
}) {
  const t = useTranslations("webhooks");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const eventLabel = useCodeLabel("webhookEvents");
  const queryClient = useQueryClient();
  const catalog = useAdministrationCatalog();
  const formId = useId();
  const [url, setUrl] = useState(webhook?.url ?? "");
  const [description, setDescription] = useState(webhook?.description ?? "");
  const [events, setEvents] = useState<WebhookEvent[] | null>(webhook?.events ?? null);
  const [active, setActive] = useState(webhook?.active ?? true);
  const [touched, setTouched] = useState(false);
  // A new endpoint listens to everything until told otherwise.
  const chosen = events ?? catalog.data?.webhookEvents ?? [];

  const save = useMutation({
    mutationFn: async (): Promise<WebhookWithSecret | null> => {
      const input = { url: url.trim(), description: description.trim(), events: chosen, active };
      if (webhook) {
        await updateWebhook(api, organization, webhook.id, input);
        return null;
      }
      return createWebhook(api, organization, input);
    },
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: integrationKeys.webhooks(organization) });
      if (!created) toast({ tone: "success", title: t("saved") });
      onSaved(created);
    },
  });
  const errors = {
    url: URL_PATTERN.test(url.trim()) ? undefined : t("urlInvalid"),
    events: chosen.length > 0 ? undefined : t("eventsRequired"),
  };
  const submit = () => {
    setTouched(true);
    if (!errors.url && !errors.events) save.mutate();
  };

  return (
    <DialogContent
      title={webhook ? t("editTitle") : t("createTitle")}
      closeLabel={tc("close")}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            {tc("cancel")}
          </Button>
          <Button variant="primary" type="submit" form={formId} loading={save.isPending}>
            {webhook ? t("save") : t("createSubmit")}
          </Button>
        </>
      }
    >
      <Form id={formId} onSubmit={submit}>
        <Field label={t("url")} error={touched ? errors.url : undefined}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              type="url"
              inputMode="url"
              value={url}
              placeholder="https://"
              autoComplete="off"
              spellCheck={false}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(event) => setUrl(event.target.value)}
            />
          )}
        </Field>
        <Field label={t("description")}>
          {({ id }) => (
            <TextInput
              id={id}
              value={description}
              maxLength={200}
              autoComplete="off"
              onChange={(event) => setDescription(event.target.value)}
            />
          )}
        </Field>
        <CheckboxGroup
          legend={t("events")}
          options={(catalog.data?.webhookEvents ?? []).map((event) => ({
            value: event,
            label: eventLabel(event),
          }))}
          value={chosen}
          onChange={(next) => setEvents(next as WebhookEvent[])}
          error={touched ? errors.events : undefined}
        />
        {webhook ? (
          <Switch label={t("active")} checked={active} onCheckedChange={setActive} />
        ) : null}
        {save.isError ? <FormError>{errorText(save.error)}</FormError> : null}
      </Form>
    </DialogContent>
  );
}
