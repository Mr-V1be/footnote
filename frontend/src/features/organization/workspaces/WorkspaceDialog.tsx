"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { useApi } from "@/shared/api/ApiProvider";
import type { Workspace } from "@/shared/api/types";
import { SLUG_MAX_LENGTH, SLUG_PATTERN, slugify } from "@/shared/format/slug";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Button } from "@/shared/ui/button/Button";
import { Dialog, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Field, TextInput } from "@/shared/ui/field/Field";
import { Form, FormError } from "@/shared/ui/form/Form";
import { Switch } from "@/shared/ui/switch/Switch";
import { useToast } from "@/shared/ui/toast/Toast";

import { adminKeys, createWorkspace, updateWorkspace } from "../queries";

/** Creating a workspace, or changing the name, address and access of one. */
export function WorkspaceDialog({
  organization,
  workspace,
  open,
  onOpenChange,
  onSaved,
}: {
  organization: string;
  /** The workspace to edit; without it a new one is created. */
  workspace?: Workspace;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (workspace: Workspace) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <WorkspaceForm
          organization={organization}
          workspace={workspace}
          onCancel={() => onOpenChange(false)}
          onSaved={(saved) => {
            onSaved?.(saved);
            onOpenChange(false);
          }}
        />
      ) : null}
    </Dialog>
  );
}

function WorkspaceForm({
  organization,
  workspace,
  onCancel,
  onSaved,
}: {
  organization: string;
  workspace?: Workspace;
  onCancel: () => void;
  onSaved: (workspace: Workspace) => void;
}) {
  const t = useTranslations("workspaces");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const router = useRouter();
  const formId = useId();
  const [name, setName] = useState(workspace?.name ?? "");
  // The address follows the name until it is edited by hand.
  const [slug, setSlug] = useState<string | null>(workspace?.slug ?? null);
  const [restricted, setRestricted] = useState(workspace?.restricted ?? false);
  const [touched, setTouched] = useState(false);
  const address = slug ?? slugify(name);

  const save = useMutation({
    mutationFn: () => {
      const input = { name: name.trim(), slug: address, restricted };
      return workspace
        ? updateWorkspace(api, organization, workspace.id, input)
        : createWorkspace(api, organization, input);
    },
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: adminKeys.workspaces(organization) });
      // The sidebar and the document lists read workspaces on the server.
      router.refresh();
      toast({
        tone: "success",
        title: workspace ? t("saved") : t("created", { name: saved.name }),
      });
      onSaved(saved);
    },
  });

  const errors = {
    name: name.trim() ? undefined : t("nameRequired"),
    slug: SLUG_PATTERN.test(address) ? undefined : t("slugInvalid"),
  };
  const submit = () => {
    setTouched(true);
    if (!errors.name && !errors.slug) save.mutate();
  };

  return (
    <DialogContent
      title={workspace ? t("editTitle") : t("createTitle")}
      closeLabel={tc("close")}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            {tc("cancel")}
          </Button>
          <Button variant="primary" type="submit" form={formId} loading={save.isPending}>
            {workspace ? t("save") : t("create")}
          </Button>
        </>
      }
    >
      <Form id={formId} onSubmit={submit}>
        <Field label={t("name")} error={touched ? errors.name : undefined}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              value={name}
              maxLength={200}
              autoComplete="off"
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
        <Field
          label={t("slug")}
          hint={t("slugHint", { slug: address || "…" })}
          error={touched ? errors.slug : undefined}
        >
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              value={address}
              maxLength={SLUG_MAX_LENGTH}
              autoComplete="off"
              spellCheck={false}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(event) => setSlug(event.target.value.toLowerCase())}
            />
          )}
        </Field>
        <Switch
          label={t("restricted")}
          hint={t("restrictedHint")}
          checked={restricted}
          onCheckedChange={setRestricted}
        />
        {save.isError ? <FormError>{errorText(save.error)}</FormError> : null}
      </Form>
    </DialogContent>
  );
}
