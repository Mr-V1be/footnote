"use client";

import { IconDotsVertical, IconKey, IconKeyOff, IconPlus } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useOrganizationAlias } from "@/features/organization/hooks";
import { useApi } from "@/shared/api/ApiProvider";
import type { ApiKey } from "@/shared/api/types";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Badge } from "@/shared/ui/badge/Badge";
import { Button } from "@/shared/ui/button/Button";
import { ConfirmDialog } from "@/shared/ui/confirm-dialog/ConfirmDialog";
import { DataList, DataListSkeleton, DataRow } from "@/shared/ui/data-list/DataList";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/shared/ui/menu/Menu";
import { Page } from "@/shared/ui/page/Page";
import { PageAction } from "@/shared/ui/page-action/PageAction";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";
import { useToast } from "@/shared/ui/toast/Toast";

import { fetchApiKeys, integrationKeys, revokeApiKey } from "../queries";
import { RevealOnceDialog } from "../RevealOnceDialog";
import { CreateKeyDialog } from "./CreateKeyDialog";

/** Keys of the organization's integrations: what each may do, revoked at once. */
export function ApiKeysScreen() {
  const t = useTranslations("apiKeys");
  const api = useApi();
  const organization = useOrganizationAlias();
  const [creating, setCreating] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<ApiKey | null>(null);
  const keys = useQuery({
    queryKey: integrationKeys.apiKeys(organization),
    queryFn: () => fetchApiKeys(api, organization),
  });
  const active = keys.data?.filter((key) => key.revokedAt === null).length ?? 0;

  function content() {
    if (keys.isPending) return <DataListSkeleton label={t("title")} rows={3} />;
    if (keys.isError) return <LoadFailure error={keys.error} onRetry={() => void keys.refetch()} />;
    if (keys.data.length === 0) {
      return (
        <StatePanel
          icon={<IconKey stroke={1.75} />}
          title={t("emptyTitle")}
          description={t("emptyDescription")}
          action={
            <Button
              variant="primary"
              icon={<IconPlus stroke={1.75} />}
              onClick={() => setCreating(true)}
            >
              {t("create")}
            </Button>
          }
        />
      );
    }
    return (
      <DataList label={t("title")} reserveActions>
        {keys.data.map((key) => (
          <ApiKeyRow key={key.id} apiKey={key} onRevoke={() => setRevoking(key)} />
        ))}
      </DataList>
    );
  }

  return (
    <Page width="narrow">
      <PageHeader
        title={t("title")}
        meta={keys.data?.length ? <span>{t("activeCount", { count: active })}</span> : null}
        actions={
          keys.data?.length ? (
            <PageAction
              icon={<IconPlus stroke={1.75} />}
              label={t("create")}
              onClick={() => setCreating(true)}
            />
          ) : undefined
        }
      />
      {content()}
      <CreateKeyDialog
        organization={organization}
        open={creating}
        onOpenChange={setCreating}
        onIssued={(issued) => setToken(issued.token)}
      />
      <RevealOnceDialog
        secret={token}
        title={t("issuedTitle")}
        label={t("token")}
        onClose={() => setToken(null)}
      />
      <RevokeKeyDialog
        organization={organization}
        apiKey={revoking}
        onClose={() => setRevoking(null)}
      />
    </Page>
  );
}

function ApiKeyRow({ apiKey, onRevoke }: { apiKey: ApiKey; onRevoke: () => void }) {
  const t = useTranslations("apiKeys");
  const scopeLabel = useCodeLabel("apiScopes");
  const formatDate = useFormatDate();
  const revoked = apiKey.revokedAt !== null;
  return (
    <DataRow
      tone={revoked ? "muted" : "default"}
      leading={revoked ? <IconKeyOff stroke={1.75} /> : <IconKey stroke={1.75} />}
      title={apiKey.name}
      description={
        <>
          <span>{t("prefix", { prefix: apiKey.prefix })}</span>
          <span>{apiKey.scopes.map(scopeLabel).join(", ")}</span>
          <span>
            {t("createdBy", { name: apiKey.createdBy, date: formatDate(apiKey.createdAt) })}
          </span>
        </>
      }
      aside={
        revoked ? (
          <Badge>{t("revoked")}</Badge>
        ) : (
          <span>
            {apiKey.lastUsedAt
              ? t("lastUsed", { date: formatDate(apiKey.lastUsedAt) })
              : t("neverUsed")}
          </span>
        )
      }
      actions={
        revoked ? undefined : (
          <Menu>
            <MenuTrigger asChild>
              <IconButton
                label={t("actionsOf", { name: apiKey.name })}
                icon={<IconDotsVertical stroke={1.75} />}
                tooltip={false}
              />
            </MenuTrigger>
            <MenuContent align="end">
              <MenuItem icon={<IconKeyOff stroke={1.75} />} tone="critical" onSelect={onRevoke}>
                {t("revoke")}
              </MenuItem>
            </MenuContent>
          </Menu>
        )
      }
    />
  );
}

function RevokeKeyDialog({
  organization,
  apiKey,
  onClose,
}: {
  organization: string;
  apiKey: ApiKey | null;
  onClose: () => void;
}) {
  const t = useTranslations("apiKeys");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const revoke = useMutation({
    mutationFn: (target: ApiKey) => revokeApiKey(api, organization, target.id),
    onSuccess: (saved) => {
      queryClient.setQueryData<ApiKey[]>(integrationKeys.apiKeys(organization), (current) =>
        current?.map((item) => (item.id === saved.id ? saved : item)),
      );
      toast({ tone: "success", title: t("revokedToast", { name: saved.name }) });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open={apiKey !== null}
      onOpenChange={(open) => {
        if (!open) {
          revoke.reset();
          onClose();
        }
      }}
      title={t("revokeTitle", { name: apiKey?.name ?? "" })}
      consequences={<p>{t("revokeConsequence")}</p>}
      confirmLabel={t("revokeConfirm")}
      cancelLabel={tc("cancel")}
      closeLabel={tc("close")}
      pending={revoke.isPending}
      error={revoke.isError ? errorText(revoke.error) : null}
      onConfirm={() => apiKey && revoke.mutate(apiKey)}
    />
  );
}
