"use client";

import {
  IconAlertTriangle,
  IconArrowLeft,
  IconDotsVertical,
  IconDownload,
  IconFileOff,
  IconHourglass,
  IconListTree,
  IconQuote,
  IconUpload,
} from "@tabler/icons-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useCan, useMembership } from "@/features/session/membership";
import { useApi } from "@/shared/api/ApiProvider";
import { ApiError } from "@/shared/api/errors";
import type { DocumentDetails } from "@/shared/api/types";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Button } from "@/shared/ui/button/Button";
import { Drawer, DrawerContent } from "@/shared/ui/drawer/Drawer";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/shared/ui/menu/Menu";
import { PageHeader } from "@/shared/ui/page-header/PageHeader";
import { Select } from "@/shared/ui/select/Select";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import {
  fetchDocument,
  fetchStructure,
  isProcessing,
  originalFileUrl,
  PROCESSING_POLL_MS,
  queryKeys,
} from "../queries";
import { StatusBadge } from "../StatusBadge";
import { UploadDialog } from "../upload/UploadDialog";
import { DocumentSheet } from "./DocumentSheet";
import styles from "./document-screen.module.css";
import { FileDetails } from "./FileDetails";
import { FootnoteProvider } from "./FootnoteContext";
import { FootnoteList } from "./FootnoteList";
import { numberFootnotes } from "./footnotes";
import { OutlineNav } from "./OutlineNav";
import { SheetSkeleton, ViewerSkeleton } from "./ViewerSkeleton";

type Panel = "outline" | "notes" | null;

function useSelectedVersion(
  details: DocumentDetails | undefined,
): [number | null, (version: number) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const requested = Number(params.get("v"));
  const known = details?.versions.some((version) => version.number === requested);
  const selected = known ? requested : (details?.latestVersion ?? null);
  const select = useCallback(
    (version: number) => router.replace(`${pathname}?v=${version}`, { scroll: false }),
    [pathname, router],
  );
  return [selected, select];
}

export function DocumentScreen({ documentId }: { documentId: string }) {
  const t = useTranslations();
  const format = useFormatter();
  const api = useApi();
  const queryClient = useQueryClient();
  const kindLabel = useCodeLabel("kinds");
  const { membership, workspaces } = useMembership();
  const organization = membership.organization.alias;
  const canUpload = useCan("documents.upload");
  const wide = useMediaQuery("(width >= 48rem)");
  const [panel, setPanel] = useState<Panel>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const details = useQuery({
    queryKey: queryKeys.details(organization, documentId),
    queryFn: () => fetchDocument(api, organization, documentId),
  });
  const [version, selectVersion] = useSelectedVersion(details.data);
  const structure = useQuery({
    queryKey: queryKeys.structure(organization, documentId, version ?? 0),
    queryFn: () => fetchStructure(api, organization, documentId, version ?? 0),
    enabled: version !== null,
    refetchInterval: (query) =>
      query.state.data && isProcessing(query.state.data.version.status)
        ? PROCESSING_POLL_MS
        : false,
  });
  const status = structure.data?.version.status;
  useEffect(() => {
    if (status === "parsed" || status === "failed") {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.documents(organization),
        refetchType: "active",
      });
    }
  }, [status, organization, queryClient]);

  const footnotes = useMemo(
    () => numberFootnotes(structure.data?.requisites ?? []),
    [structure.data],
  );
  const revealPanel = useCallback(() => {
    if (!window.matchMedia("(width >= 64rem)").matches) setPanel("notes");
  }, []);
  const listHref = `/o/${organization}/w/${details.data?.workspace.slug ?? workspaces[0]?.slug ?? "main"}/documents`;

  if (details.isPending) return <ViewerSkeleton />;
  if (details.isError) {
    const missing = details.error instanceof ApiError && details.error.isNotFound;
    return (
      <div className={styles.screen}>
        <StatePanel
          icon={missing ? <IconFileOff stroke={1.75} /> : <IconAlertTriangle stroke={1.75} />}
          tone={missing ? "neutral" : "critical"}
          role="alert"
          title={missing ? t("viewer.notFoundTitle") : t("viewer.errorTitle")}
          description={missing ? t("viewer.notFoundDescription") : t("viewer.errorDescription")}
          action={
            missing ? (
              <Button asChild variant="secondary">
                <Link href={listHref}>{t("viewer.backToList")}</Link>
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => void details.refetch()}>
                {t("common.retry")}
              </Button>
            )
          }
        />
      </div>
    );
  }

  const document = details.data;
  const versionInfo = document.versions.find((item) => item.number === version);
  const parsed =
    structure.data && structure.data.version.status === "parsed" ? structure.data : null;
  const outline = parsed?.outline ?? [];
  const download =
    version !== null ? originalFileUrl(organization, document.id, version) : undefined;

  function sheetContent() {
    if (structure.isPending || !structure.data) return <SheetSkeleton />;
    if (structure.data.version.status === "failed") {
      return (
        <StatePanel
          icon={<IconAlertTriangle stroke={1.75} />}
          tone="critical"
          role="alert"
          title={t("viewer.failedTitle")}
          description={t(`failures.${structure.data.version.failureCode ?? "internal_error"}`)}
          action={
            canUpload ? (
              <Button
                variant="primary"
                icon={<IconUpload stroke={1.75} />}
                onClick={() => setUploadOpen(true)}
              >
                {t("viewer.newVersion")}
              </Button>
            ) : undefined
          }
        />
      );
    }
    if (!parsed) {
      return (
        <div className={styles.processing}>
          <StatePanel
            icon={<IconHourglass stroke={1.75} />}
            tone="ink"
            role="status"
            title={t("viewer.processingTitle")}
            description={t("viewer.processingDescription")}
          />
          <SheetSkeleton />
        </div>
      );
    }
    return <DocumentSheet structure={parsed} footnotes={footnotes} />;
  }

  const actions = (
    <>
      {download ? (
        <Button asChild variant="secondary" icon={<IconDownload stroke={1.75} />}>
          <a href={download} download>
            {t("viewer.download")}
          </a>
        </Button>
      ) : null}
      {canUpload ? (
        <Button
          variant="secondary"
          icon={<IconUpload stroke={1.75} />}
          onClick={() => setUploadOpen(true)}
        >
          {t("viewer.newVersion")}
        </Button>
      ) : null}
    </>
  );
  const compactActions = (
    <Menu>
      <MenuTrigger asChild>
        <IconButton
          label={t("viewer.actions")}
          icon={<IconDotsVertical stroke={1.75} />}
          variant="secondary"
          tooltip={false}
        />
      </MenuTrigger>
      <MenuContent align="end">
        {download ? (
          <MenuItem asChild>
            <a href={download} download>
              <IconDownload stroke={1.75} aria-hidden />
              {t("viewer.download")}
            </a>
          </MenuItem>
        ) : null}
        {canUpload ? (
          <MenuItem icon={<IconUpload stroke={1.75} />} onSelect={() => setUploadOpen(true)}>
            {t("viewer.newVersion")}
          </MenuItem>
        ) : null}
      </MenuContent>
    </Menu>
  );

  return (
    <FootnoteProvider onRevealCard={revealPanel}>
      <div className={styles.screen}>
        <PageHeader
          leading={
            <div className={styles.leading}>
              <Link href={listHref} className={styles.back}>
                <IconArrowLeft stroke={1.75} aria-hidden />
                {t("viewer.backToList")}
              </Link>
              {wide ? null : compactActions}
            </div>
          }
          title={document.title}
          meta={
            <>
              <span>{kindLabel(document.kind)}</span>
              {versionInfo ? (
                <StatusBadge status={structure.data?.version.status ?? versionInfo.status} />
              ) : null}
              {document.versions.length > 1 && version !== null ? (
                <Select
                  label={t("viewer.versionSelect")}
                  value={String(version)}
                  onValueChange={(value) => selectVersion(Number(value))}
                  options={document.versions.map((item) => ({
                    value: String(item.number),
                    label: t("viewer.versionOption", {
                      number: item.number,
                      date: format.dateTime(new Date(item.uploadedAt), { dateStyle: "medium" }),
                    }),
                  }))}
                />
              ) : (
                <span className={styles.versionTag}>
                  {t("documents.version", { number: version ?? 1 })}
                </span>
              )}
            </>
          }
          actions={wide ? actions : undefined}
        />

        <nav className={styles.viewerBar} aria-label={t("viewer.actions")}>
          <Button
            variant="secondary"
            icon={<IconListTree stroke={1.75} />}
            onClick={() => setPanel("outline")}
          >
            {t("viewer.outline")}
          </Button>
          <span className={styles.notesToggle}>
            <Button
              variant="secondary"
              icon={<IconQuote stroke={1.75} />}
              onClick={() => setPanel("notes")}
            >
              {t("viewer.requisites")}
              <span className={styles.count}>{footnotes.length}</span>
            </Button>
          </span>
        </nav>

        <div className={styles.workspace}>
          <aside className={styles.outlineColumn} aria-label={t("viewer.outline")}>
            <h2 className={styles.columnTitle}>{t("viewer.outline")}</h2>
            <OutlineNav entries={outline} />
          </aside>
          <div className={styles.sheetColumn}>{sheetContent()}</div>
          <aside className={styles.panelColumn} aria-label={t("viewer.requisites")}>
            <section className={styles.panelSection}>
              <h2 className={styles.columnTitle}>{t("viewer.requisites")}</h2>
              <FootnoteList footnotes={footnotes} />
            </section>
            {parsed ? (
              <section className={styles.panelSection}>
                <h2 className={styles.columnTitle}>{t("viewer.details")}</h2>
                <FileDetails structure={parsed} />
              </section>
            ) : null}
          </aside>
        </div>

        <Drawer
          open={panel === "outline"}
          onOpenChange={(open) => setPanel(open ? "outline" : null)}
        >
          <DrawerContent
            side={wide ? "left" : "bottom"}
            title={t("viewer.outline")}
            closeLabel={t("common.close")}
          >
            <OutlineNav entries={outline} onNavigate={() => setPanel(null)} />
          </DrawerContent>
        </Drawer>
        <Drawer open={panel === "notes"} onOpenChange={(open) => setPanel(open ? "notes" : null)}>
          <DrawerContent
            side={wide ? "right" : "bottom"}
            title={t("viewer.requisites")}
            closeLabel={t("common.close")}
          >
            <FootnoteList footnotes={footnotes} onLocate={() => setPanel(null)} />
            {parsed ? (
              <section className={styles.drawerSection}>
                <h2 className={styles.columnTitle}>{t("viewer.details")}</h2>
                <FileDetails structure={parsed} />
              </section>
            ) : null}
          </DrawerContent>
        </Drawer>

        {canUpload ? (
          <UploadDialog
            target={{ type: "version", documentId: document.id }}
            open={uploadOpen}
            onOpenChange={setUploadOpen}
            onUploaded={(result) => selectVersion(result.versionNumber)}
          />
        ) : null}
      </div>
    </FootnoteProvider>
  );
}
