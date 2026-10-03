"use client";

import {
  IconAlertTriangle,
  IconCategory,
  IconFolder,
  IconFolderOff,
  IconSearchOff,
  IconUpload,
} from "@tabler/icons-react";
import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { PermissionScope, useCan, useMembership } from "@/features/session/membership";
import { useApi } from "@/shared/api/ApiProvider";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Button } from "@/shared/ui/button/Button";
import { Page } from "@/shared/ui/page/Page";
import { PageAction } from "@/shared/ui/page-action/PageAction";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { SearchField } from "@/shared/ui/search-field/SearchField";
import { Select } from "@/shared/ui/select/Select";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import {
  anyProcessing,
  fetchCatalog,
  fetchDocumentPage,
  PROCESSING_POLL_MS,
  queryKeys,
} from "../queries";
import { UploadDialog } from "../upload/UploadDialog";
import { DocumentList, DocumentListSkeleton } from "./DocumentList";
import { FootnoteIllustration } from "./FootnoteIllustration";
import styles from "./documents-screen.module.css";
import { useListFilters } from "./useListFilters";

const ALL_KINDS = "__all";

/** Documents of a workspace, under the role the person has in it. */
export function DocumentsScreen({ workspace }: { workspace: string }) {
  const t = useTranslations("documents");
  const { workspaces } = useMembership();
  const current = workspaces.find((item) => item.slug === workspace);
  if (!current) {
    return (
      <Page>
        <StatePanel
          icon={<IconFolderOff stroke={1.75} />}
          role="alert"
          title={t("workspaceMissingTitle")}
          description={t("workspaceMissingDescription")}
        />
      </Page>
    );
  }
  return (
    <PermissionScope permissions={current.permissions}>
      <WorkspaceDocuments workspace={workspace} />
    </PermissionScope>
  );
}

/** Choosing the workspace, when the person sees more than one. */
function WorkspaceSelect({ workspace }: { workspace: string }) {
  const t = useTranslations("documents");
  const router = useRouter();
  const { membership, workspaces } = useMembership();
  if (workspaces.length < 2) return null;
  return (
    <Select
      label={t("workspace")}
      icon={<IconFolder stroke={1.75} />}
      value={workspace}
      onValueChange={(slug) =>
        router.push(`/o/${membership.organization.alias}/w/${slug}/documents`)
      }
      options={workspaces.map((item) => ({ value: item.slug, label: item.name }))}
    />
  );
}

function WorkspaceDocuments({ workspace }: { workspace: string }) {
  const t = useTranslations("documents");
  const tc = useTranslations("common");
  const api = useApi();
  const kindLabel = useCodeLabel("kinds");
  const organization = useMembership().membership.organization.alias;
  const canUpload = useCan("documents.upload");
  const filters = useListFilters();
  const [uploadOpen, setUploadOpen] = useState(false);

  const catalog = useQuery({
    queryKey: queryKeys.catalog(),
    queryFn: () => fetchCatalog(api),
    staleTime: Infinity,
  });
  const list = useInfiniteQuery({
    queryKey: queryKeys.list(organization, workspace, filters.applied),
    queryFn: ({ pageParam }) =>
      fetchDocumentPage(api, organization, workspace, filters.applied, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor,
    // While a new filter loads, the previous results stay in place, dimmed.
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (anyProcessing(query.state.data) ? PROCESSING_POLL_MS : false),
  });

  const items = list.data?.pages.flatMap((page) => page.items) ?? [];
  const filtered = Boolean(filters.applied.search || filters.applied.kind);
  // A workspace without documents shows one action: upload the first one.
  const pristine = list.isSuccess && items.length === 0 && !filtered && !filters.search;
  const kindOptions = [
    { value: ALL_KINDS, label: t("allKinds") },
    ...(catalog.data?.kinds.map((kind) => ({ value: kind.code, label: kindLabel(kind.code) })) ??
      []),
  ];
  function content() {
    if (list.isPending) return <DocumentListSkeleton />;
    if (list.isError) {
      return (
        <StatePanel
          icon={<IconAlertTriangle stroke={1.75} />}
          tone="critical"
          role="alert"
          title={t("errorTitle")}
          description={t("errorDescription")}
          action={
            <Button variant="secondary" onClick={() => void list.refetch()}>
              {tc("retry")}
            </Button>
          }
        />
      );
    }
    if (items.length === 0 && filtered) {
      return (
        <StatePanel
          icon={<IconSearchOff stroke={1.75} />}
          title={t("noMatchesTitle")}
          description={t("noMatchesDescription")}
          action={
            <Button variant="secondary" onClick={filters.reset}>
              {t("resetFilters")}
            </Button>
          }
        />
      );
    }
    if (items.length === 0) {
      return (
        <StatePanel
          illustration={<FootnoteIllustration />}
          title={t("emptyTitle")}
          description={canUpload ? t("emptyDescription") : t("emptyReadOnly")}
          action={
            canUpload ? (
              <Button
                variant="primary"
                icon={<IconUpload stroke={1.75} />}
                onClick={() => setUploadOpen(true)}
              >
                {t("uploadDocument")}
              </Button>
            ) : undefined
          }
        />
      );
    }
    return (
      <div
        className={list.isPlaceholderData ? styles.stale : undefined}
        aria-busy={list.isPlaceholderData}
      >
        <DocumentList items={items} organization={organization} />
        {list.hasNextPage ? (
          <div className={styles.more}>
            <Button
              variant="secondary"
              loading={list.isFetchingNextPage}
              onClick={() => void list.fetchNextPage()}
            >
              {t("loadMore")}
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <Page>
      <PageHeader
        title={t("title")}
        meta={
          <>
            <WorkspaceSelect workspace={workspace} />
            {list.data && !pristine ? <span>{t("count", { count: items.length })}</span> : null}
          </>
        }
        actions={
          canUpload && !pristine ? (
            <PageAction
              icon={<IconUpload stroke={1.75} />}
              label={t("upload")}
              onClick={() => setUploadOpen(true)}
            />
          ) : undefined
        }
      />
      <div className={styles.toolbar} role="search" hidden={pristine}>
        <div className={styles.search}>
          <SearchField
            value={filters.search}
            onChange={filters.setSearch}
            label={t("search")}
            placeholder={t("searchPlaceholder")}
            clearLabel={t("clearSearch")}
          />
        </div>
        <Select
          label={t("kindFilter")}
          icon={<IconCategory stroke={1.75} />}
          value={filters.kind ?? ALL_KINDS}
          onValueChange={(value) => filters.setKind(value === ALL_KINDS ? null : value)}
          options={kindOptions}
        />
      </div>
      {content()}
      <UploadDialog
        target={{ type: "document", workspace }}
        open={uploadOpen}
        onOpenChange={setUploadOpen}
      />
    </Page>
  );
}
