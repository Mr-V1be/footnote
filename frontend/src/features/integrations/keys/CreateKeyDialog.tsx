"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { useAdministrationCatalog } from "@/features/organization/hooks";
import { useApi } from "@/shared/api/ApiProvider";
import type { ApiKey, ApiScope, IssuedKey } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Button } from "@/shared/ui/button/Button";
import { CheckboxGroup } from "@/shared/ui/checkbox-group/CheckboxGroup";
import { Dialog, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Field, TextInput } from "@/shared/ui/field/Field";
import { Form, FormError } from "@/shared/ui/form/Form";

import { createApiKey, integrationKeys } from "../queries";

/** The narrowest useful default: an integration that only reads. */
const DEFAULT_SCOPES: ApiScope[] = ["documents:read"];

export function CreateKeyDialog({
  organization,
  open,
  onOpenChange,
  onIssued,
}: {
  organization: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onIssued: (issued: IssuedKey) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <CreateKeyForm
          organization={organization}
          onCancel={() => onOpenChange(false)}
          onIssued={(issued) => {
            onOpenChange(false);
            onIssued(issued);
          }}
        />
      ) : null}
    </Dialog>
  );
}

function CreateKeyForm({
  organization,
  onCancel,
  onIssued,
}: {
  organization: string;
  onCancel: () => void;
  onIssued: (issued: IssuedKey) => void;
}) {
  const t = useTranslations("apiKeys");
  const tc = useTranslations("common");
  const api = useApi();
  const errorText = useErrorText();
  const scopeLabel = useCodeLabel("apiScopes");
  const queryClient = useQueryClient();
  const catalog = useAdministrationCatalog();
  const formId = useId();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<ApiScope[]>(DEFAULT_SCOPES);
  const [touched, setTouched] = useState(false);

  const create = useMutation({
    mutationFn: () => createApiKey(api, organization, name.trim(), scopes),
    onSuccess: (issued) => {
      queryClient.setQueryData<ApiKey[]>(integrationKeys.apiKeys(organization), (current) =>
        current ? [issued.key, ...current] : current,
      );
      onIssued(issued);
    },
  });
  const errors = {
    name: name.trim() ? undefined : t("nameRequired"),
    scopes: scopes.length > 0 ? undefined : t("scopesRequired"),
  };
  const submit = () => {
    setTouched(true);
    if (!errors.name && !errors.scopes) create.mutate();
  };

  return (
    <DialogContent
      title={t("createTitle")}
      closeLabel={tc("close")}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            {tc("cancel")}
          </Button>
          <Button variant="primary" type="submit" form={formId} loading={create.isPending}>
            {t("createSubmit")}
          </Button>
        </>
      }
    >
      <Form id={formId} onSubmit={submit}>
        <Field label={t("name")} hint={t("nameHint")} error={touched ? errors.name : undefined}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              value={name}
              maxLength={100}
              autoComplete="off"
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
        <CheckboxGroup
          legend={t("scopes")}
          options={(catalog.data?.apiScopes ?? []).map((scope) => ({
            value: scope,
            label: scopeLabel(scope),
          }))}
          value={scopes}
          onChange={(next) => setScopes(next as ApiScope[])}
          error={touched ? errors.scopes : undefined}
        />
        {create.isError ? <FormError>{errorText(create.error)}</FormError> : null}
      </Form>
    </DialogContent>
  );
}
