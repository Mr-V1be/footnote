"use client";

import {
  IconDotsVertical,
  IconPencil,
  IconTrash,
  IconUserMinus,
  IconUserPlus,
  IconUsers,
} from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useApi } from "@/shared/api/ApiProvider";
import { ApiError } from "@/shared/api/errors";
import type { Member, WorkspaceMember } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Avatar } from "@/shared/ui/avatar/Avatar";
import { BackLink } from "@/shared/ui/back-link/BackLink";
import { Badge } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { DataList, DataListSkeleton, DataRow } from "@/shared/ui/data-list/DataList";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/shared/ui/menu/Menu";
import { Page } from "@/shared/ui/page/Page";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Section } from "@/shared/ui/section/Section";
import { Select } from "@/shared/ui/select/Select";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";
import { useToast } from "@/shared/ui/toast/Toast";

import styles from "../organization.module.css";
import { useOrganizationAlias, useRoleOptions } from "../hooks";
import {
  adminKeys,
  fetchMembers,
  fetchWorkspaceMembers,
  fetchWorkspaces,
  removeWorkspaceMember,
  setWorkspaceMember,
} from "../queries";
import { AddWorkspaceMemberDialog } from "./AddWorkspaceMemberDialog";
import { WorkspaceDialog } from "./WorkspaceDialog";
import { DeleteWorkspaceDialog } from "./WorkspacesScreen";

/** One workspace: who works in it and with which role. */
export function WorkspaceScreen({ workspaceId }: { workspaceId: string }) {
  const t = useTranslations("workspaces");
  const api = useApi();
  const router = useRouter();
  const organization = useOrganizationAlias();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [adding, setAdding] = useState(false);
  const workspaces = useQuery({
    queryKey: adminKeys.workspaces(organization),
    queryFn: () => fetchWorkspaces(api, organization),
  });
  const members = useQuery({
    queryKey: adminKeys.members(organization),
    queryFn: () => fetchMembers(api, organization),
  });
  const assigned = useQuery({
    queryKey: adminKeys.workspaceMembers(organization, workspaceId),
    queryFn: () => fetchWorkspaceMembers(api, organization, workspaceId),
  });
  const listHref = `/o/${organization}/settings/workspaces`;
  const back = <BackLink href={listHref} label={t("title")} />;

  if (workspaces.isPending) {
    return (
      <Page width="narrow" busy>
        <Skeleton width="14rem" height="2rem" />
        <DataListSkeleton label={t("members")} rows={3} />
      </Page>
    );
  }
  const workspace = workspaces.data?.find((item) => item.id === workspaceId);
  if (workspaces.isError || !workspace) {
    return (
      <Page width="narrow">
        <LoadFailure
          error={workspaces.error ?? new ApiError(404, "workspace_not_found")}
          onRetry={() => void workspaces.refetch()}
        />
      </Page>
    );
  }

  const people = new Map((members.data ?? []).map((member) => [member.userId, member]));
  const candidates = (members.data ?? []).filter(
    (member) => !assigned.data?.some((item) => item.userId === member.userId),
  );

  function content() {
    if (assigned.isPending || members.isPending) {
      return <DataListSkeleton label={t("members")} rows={3} />;
    }
    if (assigned.isError || members.isError) {
      return (
        <LoadFailure
          error={assigned.error ?? members.error}
          onRetry={() => void Promise.all([assigned.refetch(), members.refetch()])}
        />
      );
    }
    if (assigned.data.length === 0) {
      return (
        <StatePanel
          icon={<IconUsers stroke={1.75} />}
          title={t("noMembersTitle")}
          description={workspace?.restricted ? t("noMembersRestricted") : t("noMembersOpen")}
        />
      );
    }
    return (
      <DataList label={t("members")}>
        {assigned.data.map((item) => (
          <WorkspaceMemberRow
            key={item.userId}
            organization={organization}
            workspaceId={workspaceId}
            assignment={item}
            member={people.get(item.userId)}
          />
        ))}
      </DataList>
    );
  }

  return (
    <Page width="narrow">
      <PageHeader
        leading={back}
        title={workspace.name}
        meta={
          <>
            <span>/w/{workspace.slug}</span>
            <span>{t("documents", { count: workspace.documents })}</span>
            <Badge tone={workspace.restricted ? "ink" : "neutral"}>
              {workspace.restricted ? t("restrictedBadge") : t("openBadge")}
            </Badge>
          </>
        }
        actions={
          <Menu>
            <MenuTrigger asChild>
              <IconButton
                label={t("actionsOf", { name: workspace.name })}
                icon={<IconDotsVertical stroke={1.75} />}
                variant="secondary"
                tooltip={false}
              />
            </MenuTrigger>
            <MenuContent align="end">
              <MenuItem icon={<IconPencil stroke={1.75} />} onSelect={() => setEditing(true)}>
                {t("edit")}
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
        }
      />
      <Section
        title={t("members")}
        meta={workspace.restricted ? t("othersHidden") : t("othersOrganizationRole")}
        actions={
          candidates.length > 0 ? (
            <Button
              variant="secondary"
              icon={<IconUserPlus stroke={1.75} />}
              onClick={() => setAdding(true)}
            >
              {t("addMember")}
            </Button>
          ) : null
        }
      >
        {content()}
      </Section>
      <AddWorkspaceMemberDialog
        organization={organization}
        workspaceId={workspaceId}
        candidates={candidates}
        open={adding}
        onOpenChange={setAdding}
      />
      <WorkspaceDialog
        organization={organization}
        workspace={workspace}
        open={editing}
        onOpenChange={setEditing}
      />
      <DeleteWorkspaceDialog
        organization={organization}
        workspace={deleting ? workspace : null}
        onClose={() => setDeleting(false)}
        onDeleted={() => router.push(listHref)}
      />
    </Page>
  );
}

function WorkspaceMemberRow({
  organization,
  workspaceId,
  assignment,
  member,
}: {
  organization: string;
  workspaceId: string;
  assignment: WorkspaceMember;
  member: Member | undefined;
}) {
  const t = useTranslations("workspaces");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const roleLabel = useCodeLabel("roles");
  const queryClient = useQueryClient();
  const roleOptions = useRoleOptions();
  const key = adminKeys.workspaceMembers(organization, workspaceId);
  const name = member?.displayName ?? tc("unknownUser");

  const change = useMutation({
    mutationFn: (role: string) =>
      setWorkspaceMember(api, organization, workspaceId, assignment.userId, role),
    onMutate: async (role) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<WorkspaceMember[]>(key);
      queryClient.setQueryData<WorkspaceMember[]>(key, (current) =>
        current?.map((item) => (item.userId === assignment.userId ? { ...item, role } : item)),
      );
      return { previous };
    },
    onError: (error, _role, context) => {
      queryClient.setQueryData(key, context?.previous);
      toast({ tone: "critical", title: t("roleNotChanged"), description: errorText(error) });
    },
  });
  const remove = useMutation({
    mutationFn: () => removeWorkspaceMember(api, organization, workspaceId, assignment.userId),
    onSuccess: () => {
      queryClient.setQueryData<WorkspaceMember[]>(key, (current) =>
        current?.filter((item) => item.userId !== assignment.userId),
      );
      toast({ tone: "success", title: t("memberRemoved", { name }) });
    },
    onError: (error) =>
      toast({ tone: "critical", title: t("memberNotRemoved"), description: errorText(error) }),
  });

  return (
    <DataRow
      leading={<Avatar name={name} />}
      title={name}
      description={
        <>
          {member?.email ? <span>{member.email}</span> : null}
          {member?.role ? (
            <span>{t("organizationRole", { role: roleLabel(member.role) })}</span>
          ) : null}
        </>
      }
      aside={
        <div className={styles.role}>
          <Select
            block
            size="sm"
            label={t("roleOf", { name })}
            value={assignment.role}
            onValueChange={(role) => change.mutate(role)}
            options={roleOptions}
          />
        </div>
      }
      actions={
        <Menu>
          <MenuTrigger asChild>
            <IconButton
              label={t("memberActionsOf", { name })}
              icon={<IconDotsVertical stroke={1.75} />}
              tooltip={false}
            />
          </MenuTrigger>
          <MenuContent align="end">
            <MenuItem
              icon={<IconUserMinus stroke={1.75} />}
              tone="critical"
              onSelect={() => remove.mutate()}
            >
              {t("removeMember")}
            </MenuItem>
          </MenuContent>
        </Menu>
      }
    />
  );
}
