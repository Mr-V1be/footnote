"use client";

import {
  IconDotsVertical,
  IconFolder,
  IconFolderPlus,
  IconLock,
  IconPencil,
  IconTrash,
} from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useApi } from "@/shared/api/ApiProvider";
import type { Workspace } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Badge } from "@/shared/ui/badge/Badge";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog/ConfirmDialog";
import { DataList, DataListSkeleton, DataRow, DataRowLink } from "@/shared/ui/data-list/DataList";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/shared/ui/menu/Menu";
import { Page } from "@/shared/ui/page/Page";
import { PageAction } from "@/shared/ui/page-action/PageAction";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { useToast } from "@/shared/ui/toast/Toast";

import { useOrganizationAlias } from "../hooks";
import { adminKeys, deleteWorkspace, fetchWorkspaces } from "../queries";
import { WorkspaceDialog } from "./WorkspaceDialog";

/** Workspaces of the organization: open to everyone, or only to those listed. */
export function WorkspacesScreen() {
  const t = useTranslations("workspaces");
  const api = useApi();
  const organization = useOrganizationAlias();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Workspace | null>(null);
  const [deleting, setDeleting] = useState<Workspace | null>(null);
  const workspaces = useQuery({
    queryKey: adminKeys.workspaces(organization),
    queryFn: () => fetchWorkspaces(api, organization),
  });

  function content() {
    if (workspaces.isPending) return <DataListSkeleton label={t("title")} rows={3} />;
    if (workspaces.isError) {
      return <LoadFailure error={workspaces.error} onRetry={() => void workspaces.refetch()} />;
    }
    return (
      <DataList label={t("title")}>
        {workspaces.data.map((workspace) => (
          <WorkspaceRow
            key={workspace.id}
            workspace={workspace}
            organization={organization}
            onEdit={() => setEditing(workspace)}
            onDelete={() => setDeleting(workspace)}
          />
        ))}
      </DataList>
    );
  }

  return (
    <Page width="narrow">
      <PageHeader
        title={t("title")}
        meta={workspaces.data ? <span>{t("count", { count: workspaces.data.length })}</span> : null}
        actions={
          workspaces.isSuccess ? (
            <PageAction
              icon={<IconFolderPlus stroke={1.75} />}
              label={t("createAction")}
              onClick={() => setCreating(true)}
            />
          ) : undefined
        }
      />
      {content()}
      <WorkspaceDialog organization={organization} open={creating} onOpenChange={setCreating} />
      <WorkspaceDialog
        organization={organization}
        workspace={editing ?? undefined}
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
      />
      <DeleteWorkspaceDialog
        organization={organization}
        workspace={deleting}
        onClose={() => setDeleting(null)}
      />
    </Page>
  );
}

function WorkspaceRow({
  workspace,
  organization,
  onEdit,
  onDelete,
}: {
  workspace: Workspace;
  organization: string;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const t = useTranslations("workspaces");
  const roleLabel = useCodeLabel("roles");
  return (
    <DataRow
      leading={workspace.restricted ? <IconLock stroke={1.75} /> : <IconFolder stroke={1.75} />}
      title={
        <DataRowLink href={`/o/${organization}/settings/workspaces/${workspace.id}`}>
          {workspace.name}
        </DataRowLink>
      }
      description={
        <>
          <span>/w/{workspace.slug}</span>
          <span>{t("documents", { count: workspace.documents })}</span>
        </>
      }
      aside={
        <>
          <Badge tone={workspace.restricted ? "ink" : "neutral"}>
            {workspace.restricted ? t("restrictedBadge") : t("openBadge")}
          </Badge>
          <span>{roleLabel(workspace.role)}</span>
        </>
      }
      actions={
        <Menu>
          <MenuTrigger asChild>
            <IconButton
              label={t("actionsOf", { name: workspace.name })}
              icon={<IconDotsVertical stroke={1.75} />}
              tooltip={false}
            />
          </MenuTrigger>
          <MenuContent align="end">
            <MenuItem icon={<IconPencil stroke={1.75} />} onSelect={onEdit}>
              {t("edit")}
            </MenuItem>
            <MenuItem icon={<IconTrash stroke={1.75} />} tone="critical" onSelect={onDelete}>
              {t("delete")}
            </MenuItem>
          </MenuContent>
        </Menu>
      }
    />
  );
}

export function DeleteWorkspaceDialog({
  organization,
  workspace,
  onClose,
  onDeleted,
}: {
  organization: string;
  workspace: Workspace | null;
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const t = useTranslations("workspaces");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const router = useRouter();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: (target: Workspace) => deleteWorkspace(api, organization, target.id),
    onSuccess: async (_result, target) => {
      await queryClient.invalidateQueries({ queryKey: adminKeys.workspaces(organization) });
      router.refresh();
      toast({ tone: "success", title: t("deleted", { name: target.name }) });
      onClose();
      onDeleted?.();
    },
  });
  return (
    <ConfirmDialog
      open={workspace !== null}
      onOpenChange={(open) => {
        if (!open) {
          remove.reset();
          onClose();
        }
      }}
      title={t("deleteTitle", { name: workspace?.name ?? "" })}
      consequences={
        <p>
          {workspace && workspace.documents > 0
            ? t("deleteBlocked", { count: workspace.documents })
            : t("deleteConsequence")}
        </p>
      }
      confirmLabel={t("deleteConfirm")}
      cancelLabel={tc("cancel")}
      closeLabel={tc("close")}
      pending={remove.isPending}
      error={remove.isError ? errorText(remove.error) : null}
      onConfirm={() => workspace && remove.mutate(workspace)}
    />
  );
}
