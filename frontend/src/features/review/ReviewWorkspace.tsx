"use client";

import { IconListCheck, IconListTree, IconQuote } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";

import { CheckSummary } from "@/features/checks/result/CheckSummary";
import type { CardHandlers } from "@/features/checks/result/FindingList";
import { useCheckReport, useFindingReview } from "@/features/checks/useCheckReport";
import { isRunPending } from "@/features/checks/queries";
import { useCan } from "@/features/session/membership";
import { DocumentSheet } from "@/features/documents/viewer/sheet/DocumentSheet";
import {
  FootnoteProvider,
  useFootnotes,
  type CardPlace,
} from "@/features/documents/viewer/FootnoteContext";
import { OutlineNav } from "@/features/documents/viewer/OutlineNav";
import type { DocumentStructure } from "@/shared/api/types";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { Button } from "@/shared/ui/button/Button";
import { Drawer, DrawerContent } from "@/shared/ui/drawer/Drawer";

import { NotesPanel } from "./NotesPanel";
import styles from "./review.module.css";
import { useReviewState, type NotesMode, type ReviewState } from "./useReviewState";

type Panel = "outline" | "notes" | null;

/** Where the margin is a column beside the sheet rather than a drawer. */
const MARGIN_QUERY = "(width >= 64rem)";

function useCardHandlers(
  state: ReviewState,
  organization: string,
  documentId: string,
  version: number,
  onLocated: () => void,
): CardHandlers {
  const review = useFindingReview(organization, documentId, version);
  const { active, setActive, revealMark } = useFootnotes();
  return useMemo(
    () => ({
      selectedId: state.selectedId,
      busyId: review.isPending ? (review.variables?.finding.id ?? null) : null,
      activeNumber: active,
      onSelect: state.select,
      onHover: setActive,
      onReview: (item, status) => review.mutate({ finding: item.finding, review: status }),
      onLocate: (item) => {
        if (!item.footnote) return;
        const number = item.footnote.number;
        onLocated();
        window.requestAnimationFrame(() => revealMark(number));
      },
    }),
    [state.selectedId, state.select, review, active, setActive, revealMark, onLocated],
  );
}

function Workspace({
  organization,
  documentId,
  version,
  structure,
  state,
  completed,
  panel,
  setPanel,
}: {
  organization: string;
  documentId: string;
  version: number;
  structure: DocumentStructure;
  state: ReviewState;
  /** The latest run finished: an empty margin means "no findings", not "not yet". */
  completed: boolean;
  panel: Panel;
  setPanel: (panel: Panel) => void;
}) {
  const t = useTranslations();
  const wide = useMediaQuery("(width >= 48rem)");
  const margin = useMediaQuery(MARGIN_QUERY);
  const [sheet, setSheet] = useState<HTMLElement | null>(null);
  const closePanel = useCallback(() => setPanel(null), [setPanel]);
  const handlers = useCardHandlers(state, organization, documentId, version, closePanel);
  const openNotes = (mode: NotesMode) => {
    state.setMode(mode);
    setPanel("notes");
  };
  const findingCount = state.visible.length;

  return (
    <>
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
            icon={<IconListCheck stroke={1.75} />}
            onClick={() => openNotes("findings")}
          >
            {t("checks.findings")}
            <span className={styles.count}>{findingCount}</span>
          </Button>
        </span>
        <span className={styles.notesToggle}>
          <Button
            variant="secondary"
            icon={<IconQuote stroke={1.75} />}
            onClick={() => openNotes("requisites")}
          >
            {t("viewer.requisites")}
          </Button>
        </span>
      </nav>

      <div className={styles.workspace}>
        <aside className={styles.outlineColumn} aria-label={t("viewer.outline")}>
          <h2 className={styles.columnTitle}>{t("viewer.outline")}</h2>
          <OutlineNav entries={structure.outline} />
        </aside>
        <div className={styles.sheetColumn}>
          <DocumentSheet structure={structure} footnotes={state.footnotes} sheetRef={setSheet} />
        </div>
        {margin ? (
          <aside className={styles.marginColumn} aria-label={t("checks.findings")}>
            <NotesPanel
              state={state}
              structure={structure}
              handlers={handlers}
              layout="column"
              sheet={sheet}
              checked={completed}
            />
          </aside>
        ) : null}
      </div>

      <Drawer open={panel === "outline"} onOpenChange={(open) => setPanel(open ? "outline" : null)}>
        <DrawerContent
          side={wide ? "left" : "bottom"}
          title={t("viewer.outline")}
          closeLabel={t("common.close")}
        >
          <OutlineNav entries={structure.outline} onNavigate={closePanel} />
        </DrawerContent>
      </Drawer>
      {margin ? null : (
        <Drawer open={panel === "notes"} onOpenChange={(open) => setPanel(open ? "notes" : null)}>
          <DrawerContent
            side={wide ? "right" : "bottom"}
            title={state.mode === "findings" ? t("checks.findings") : t("viewer.requisites")}
            closeLabel={t("common.close")}
          >
            <NotesPanel
              state={state}
              structure={structure}
              handlers={handlers}
              layout="drawer"
              sheet={null}
              checked={completed}
              onLocateRequisite={closePanel}
            />
          </DrawerContent>
        </Drawer>
      )}
    </>
  );
}

/**
 * The result of a check: the document in the middle, markers of findings in
 * its text and the findings themselves in the margin — beside the sheet on a
 * wide screen, in a bottom sheet on a phone.
 */
export function ReviewWorkspace({
  organization,
  documentId,
  version,
  structure,
}: {
  organization: string;
  documentId: string;
  version: number;
  structure: DocumentStructure;
}) {
  const { report, recheck } = useCheckReport(organization, documentId, version);
  const data = report.data ?? null;
  const state = useReviewState(structure, data);
  const canRecheck = useCan("checks.run");
  const [panel, setPanel] = useState<Panel>(null);
  const settled = data ? !isRunPending(data.run.status) : false;

  // A marker in the text opens its finding: in the margin, or in the drawer.
  const revealCard = useCallback(
    (number: number): CardPlace => {
      if (state.mode === "findings") {
        const item = state.byNumber(number);
        if (item) state.setSelectedId(item.finding.id);
      }
      if (window.matchMedia(MARGIN_QUERY).matches) return "margin";
      setPanel("notes");
      return "panel";
    },
    [state],
  );

  return (
    <FootnoteProvider onRevealCard={revealCard}>
      <div className={styles.review}>
        <CheckSummary
          report={data}
          counts={state.counts}
          tally={state.tally}
          reviews={state.reviews}
          canRecheck={canRecheck && (settled || data === null) && !report.isPending}
          rechecking={recheck.isPending}
          onRecheck={() => recheck.mutate()}
        />
        <Workspace
          organization={organization}
          documentId={documentId}
          version={version}
          structure={structure}
          state={state}
          completed={data?.run.status === "completed"}
          panel={panel}
          setPanel={setPanel}
        />
      </div>
    </FootnoteProvider>
  );
}
