"use client";

import { IconDotsVertical, IconUserMinus, IconUserPlus } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useSession } from "@/features/session/session";
import { useApi } from "@/shared/api/ApiProvider";
import type { Member } from "@/shared/api/types";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Avatar } from "@/shared/ui/avatar/Avatar";
import { Badge } from "@/shared/ui/badge/Badge";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog/ConfirmDialog";
import { DataList, DataListSkeleton, DataRow } from "@/shared/ui/data-list/DataList";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/shared/ui/menu/Menu";
import { Page } from "@/shared/ui/page/Page";
import { PageAction } from "@/shared/ui/page-action/PageAction";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Select } from "@/shared/ui/select/Select";
import { useToast } from "@/shared/ui/toast/Toast";

import styles from "../organization.module.css";
import { useOrganizationAlias, useRoleOptions } from "../hooks";
import { adminKeys, changeMemberRole, fetchMembers, removeMember } from "../queries";
import { InviteDialog } from "./InviteDialog";

/** People of the organization and their roles; the owner invites and removes them. */
export function MembersScreen() {
  const t = useTranslations("members");
  const api = useApi();
  const organization = useOrganizationAlias();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [removing, setRemoving] = useState<Member | null>(null);
  const members = useQuery({
    queryKey: adminKeys.members(organization),
    queryFn: () => fetchMembers(api, organization),
  });

  function content() {
    if (members.isPending) return <DataListSkeleton label={t("title")} rows={5} />;
    if (members.isError) {
      return <LoadFailure error={members.error} onRetry={() => void members.refetch()} />;
    }
    return (
      <DataList label={t("title")} reserveActions>
        {members.data.map((member) => (
          <MemberRow
            key={member.userId}
            member={member}
            organization={organization}
            onRemove={() => setRemoving(member)}
          />
        ))}
      </DataList>
    );
  }

  return (
    <Page width="narrow">
      <PageHeader
        title={t("title")}
        meta={members.data ? <span>{t("count", { count: members.data.length })}</span> : null}
        actions={
          members.isSuccess ? (
            <PageAction
              icon={<IconUserPlus stroke={1.75} />}
              label={t("invite")}
              onClick={() => setInviteOpen(true)}
            />
          ) : undefined
        }
      />
      {content()}
      <InviteDialog organization={organization} open={inviteOpen} onOpenChange={setInviteOpen} />
      <RemoveMemberDialog
        organization={organization}
        member={removing}
        onClose={() => setRemoving(null)}
      />
    </Page>
  );
}

function MemberRow({
  member,
  organization,
  onRemove,
}: {
  member: Member;
  organization: string;
  onRemove: () => void;
}) {
  const t = useTranslations("members");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const me = useSession();
  const roleOptions = useRoleOptions();
  const key = adminKeys.members(organization);
  const isMe = member.userId === me.id;

  // The new role shows at once; a refusal (the last owner) puts the old one back.
  const change = useMutation({
    mutationFn: (role: string) => changeMemberRole(api, organization, member.userId, role),
    onMutate: async (role) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Member[]>(key);
      queryClient.setQueryData<Member[]>(key, (current) =>
        current?.map((item) => (item.userId === member.userId ? { ...item, role } : item)),
      );
      return { previous };
    },
    onError: (error, _role, context) => {
      queryClient.setQueryData(key, context?.previous);
      toast({ tone: "critical", title: t("roleNotChanged"), description: errorText(error) });
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<Member[]>(key, (current) =>
        current?.map((item) => (item.userId === saved.userId ? saved : item)),
      );
      toast({ tone: "success", title: t("roleChanged", { name: saved.displayName }) });
    },
  });

  return (
    <DataRow
      leading={<Avatar name={member.displayName} />}
      title={member.displayName}
      description={
        <>
          {member.email ? <span>{member.email}</span> : null}
          {isMe ? <Badge>{t("you")}</Badge> : null}
          {member.pending ? <Badge tone="important">{t("pending")}</Badge> : null}
        </>
      }
      aside={
        <div className={styles.role}>
          <Select
            block
            size="sm"
            label={t("roleOf", { name: member.displayName })}
            value={member.role ?? ""}
            onValueChange={(role) => change.mutate(role)}
            options={roleOptions}
          />
        </div>
      }
      actions={
        isMe ? undefined : (
          <Menu>
            <MenuTrigger asChild>
              <IconButton
                label={t("actionsOf", { name: member.displayName })}
                icon={<IconDotsVertical stroke={1.75} />}
                tooltip={false}
              />
            </MenuTrigger>
            <MenuContent align="end">
              <MenuItem icon={<IconUserMinus stroke={1.75} />} tone="critical" onSelect={onRemove}>
                {t("remove")}
              </MenuItem>
            </MenuContent>
          </Menu>
        )
      }
    />
  );
}

function RemoveMemberDialog({
  organization,
  member,
  onClose,
}: {
  organization: string;
  member: Member | null;
  onClose: () => void;
}) {
  const t = useTranslations("members");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: (target: Member) => removeMember(api, organization, target.userId),
    onSuccess: (_result, target) => {
      queryClient.setQueryData<Member[]>(adminKeys.members(organization), (current) =>
        current?.filter((item) => item.userId !== target.userId),
      );
      toast({ tone: "success", title: t("removed", { name: target.displayName }) });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open={member !== null}
      onOpenChange={(open) => {
        if (!open) {
          remove.reset();
          onClose();
        }
      }}
      title={t("removeTitle", { name: member?.displayName ?? "" })}
      consequences={
        <>
          <p>{t("removeConsequence")}</p>
          <p>{t("removeKept")}</p>
        </>
      }
      confirmLabel={t("removeConfirm")}
      cancelLabel={tc("cancel")}
      closeLabel={tc("close")}
      pending={remove.isPending}
      error={remove.isError ? errorText(remove.error) : null}
      onConfirm={() => member && remove.mutate(member)}
    />
  );
}
