"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { useApi } from "@/shared/api/ApiProvider";
import type { Member, WorkspaceMember } from "@/shared/api/types";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Button } from "@/shared/ui/button/Button";
import { Dialog, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Field } from "@/shared/ui/field/Field";
import { Form, FormError } from "@/shared/ui/form/Form";
import { Select } from "@/shared/ui/select/Select";
import { useToast } from "@/shared/ui/toast/Toast";

import { defaultRole, useAdministrationCatalog, useRoleOptions } from "../hooks";
import { adminKeys, setWorkspaceMember } from "../queries";

/** Giving a member of the organization a role in one workspace. */
export function AddWorkspaceMemberDialog({
  organization,
  workspaceId,
  candidates,
  open,
  onOpenChange,
}: {
  organization: string;
  workspaceId: string;
  /** Members of the organization not yet listed in the workspace. */
  candidates: readonly Member[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <AddForm
          organization={organization}
          workspaceId={workspaceId}
          candidates={candidates}
          onDone={() => onOpenChange(false)}
        />
      ) : null}
    </Dialog>
  );
}

function AddForm({
  organization,
  workspaceId,
  candidates,
  onDone,
}: {
  organization: string;
  workspaceId: string;
  candidates: readonly Member[];
  onDone: () => void;
}) {
  const t = useTranslations("workspaces");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const formId = useId();
  const catalog = useAdministrationCatalog();
  const roleOptions = useRoleOptions();
  const [userId, setUserId] = useState(candidates[0]?.userId ?? "");
  const [role, setRole] = useState<string | null>(null);
  const selectedRole = role ?? defaultRole(catalog.data?.roles ?? []);
  const person = candidates.find((member) => member.userId === userId);

  const add = useMutation({
    mutationFn: () => setWorkspaceMember(api, organization, workspaceId, userId, selectedRole),
    onSuccess: (saved: WorkspaceMember) => {
      queryClient.setQueryData<WorkspaceMember[]>(
        adminKeys.workspaceMembers(organization, workspaceId),
        (current) => (current ? [...current, saved] : [saved]),
      );
      toast({ tone: "success", title: t("memberAdded", { name: person?.displayName ?? "" }) });
      onDone();
    },
  });

  return (
    <DialogContent
      title={t("addMemberTitle")}
      closeLabel={tc("close")}
      footer={
        <>
          <Button variant="secondary" onClick={onDone}>
            {tc("cancel")}
          </Button>
          <Button
            variant="primary"
            type="submit"
            form={formId}
            loading={add.isPending}
            disabled={!userId || !selectedRole}
          >
            {t("addMemberSubmit")}
          </Button>
        </>
      }
    >
      <Form id={formId} onSubmit={() => add.mutate()}>
        <Field label={t("person")}>
          {({ id }) => (
            <Select
              id={id}
              block
              value={userId}
              onValueChange={setUserId}
              options={candidates.map((member) => ({
                value: member.userId,
                label: member.displayName,
              }))}
            />
          )}
        </Field>
        <Field label={t("roleInWorkspace")}>
          {({ id }) => (
            <Select
              id={id}
              block
              value={selectedRole}
              onValueChange={setRole}
              options={roleOptions}
            />
          )}
        </Field>
        {add.isError ? <FormError>{errorText(add.error)}</FormError> : null}
      </Form>
    </DialogContent>
  );
}
