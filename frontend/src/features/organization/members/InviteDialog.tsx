"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { useApi } from "@/shared/api/ApiProvider";
import type { Member } from "@/shared/api/types";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Button } from "@/shared/ui/button/Button";
import { Dialog, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Field, TextInput } from "@/shared/ui/field/Field";
import { Form, FormError, FormRow } from "@/shared/ui/form/Form";
import { Select } from "@/shared/ui/select/Select";
import { useToast } from "@/shared/ui/toast/Toast";

import { defaultRole, useAdministrationCatalog, useRoleOptions } from "../hooks";
import { adminKeys, inviteMember } from "../queries";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function InviteDialog({
  organization,
  open,
  onOpenChange,
}: {
  organization: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? <InviteForm organization={organization} onDone={() => onOpenChange(false)} /> : null}
    </Dialog>
  );
}

function InviteForm({ organization, onDone }: { organization: string; onDone: () => void }) {
  const t = useTranslations("members");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const formId = useId();
  const catalog = useAdministrationCatalog();
  const roleOptions = useRoleOptions();
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [role, setRole] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const selectedRole = role ?? defaultRole(catalog.data?.roles ?? []);

  const invite = useMutation({
    mutationFn: () =>
      inviteMember(api, organization, {
        email: email.trim(),
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        role: selectedRole,
      }),
    onSuccess: (member: Member) => {
      queryClient.setQueryData<Member[]>(adminKeys.members(organization), (current) =>
        current ? [...current.filter((item) => item.userId !== member.userId), member] : current,
      );
      void queryClient.invalidateQueries({ queryKey: adminKeys.members(organization) });
      toast({
        tone: "success",
        title: member.pending ? t("invited", { email: member.email ?? "" }) : t("added"),
      });
      onDone();
    },
  });

  const errors = {
    email: EMAIL.test(email.trim()) ? undefined : t("emailInvalid"),
    firstName: firstName.trim() ? undefined : t("required"),
    lastName: lastName.trim() ? undefined : t("required"),
  };
  const valid = !errors.email && !errors.firstName && !errors.lastName && Boolean(selectedRole);
  const submit = () => {
    setTouched(true);
    if (valid) invite.mutate();
  };

  return (
    <DialogContent
      title={t("inviteTitle")}
      closeLabel={tc("close")}
      footer={
        <>
          <Button variant="secondary" onClick={onDone}>
            {tc("cancel")}
          </Button>
          <Button variant="primary" type="submit" form={formId} loading={invite.isPending}>
            {t("inviteSubmit")}
          </Button>
        </>
      }
    >
      <Form id={formId} onSubmit={submit}>
        <Field label={t("email")} error={touched ? errors.email : undefined}>
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              type="email"
              autoComplete="off"
              inputMode="email"
              value={email}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              onChange={(event) => setEmail(event.target.value)}
            />
          )}
        </Field>
        <FormRow>
          <Field label={t("firstName")} error={touched ? errors.firstName : undefined}>
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                value={firstName}
                autoComplete="off"
                maxLength={100}
                aria-describedby={describedBy}
                aria-invalid={invalid}
                onChange={(event) => setFirstName(event.target.value)}
              />
            )}
          </Field>
          <Field label={t("lastName")} error={touched ? errors.lastName : undefined}>
            {({ id, describedBy, invalid }) => (
              <TextInput
                id={id}
                value={lastName}
                autoComplete="off"
                maxLength={100}
                aria-describedby={describedBy}
                aria-invalid={invalid}
                onChange={(event) => setLastName(event.target.value)}
              />
            )}
          </Field>
        </FormRow>
        <Field label={t("role")}>
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
        {invite.isError ? <FormError>{errorText(invite.error)}</FormError> : null}
      </Form>
    </DialogContent>
  );
}
