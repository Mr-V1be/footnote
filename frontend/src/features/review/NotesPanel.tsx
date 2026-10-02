"use client";

import { IconListCheck, IconQuote } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { FindingFilters } from "@/features/checks/result/FindingFilters";
import { FindingList, type CardHandlers } from "@/features/checks/result/FindingList";
import { SidenoteColumn } from "@/features/checks/result/SidenoteColumn";
import { DEFAULT_FILTERS } from "@/features/checks/findings";
import { FileDetails } from "@/features/documents/viewer/FileDetails";
import { RequisiteNotes } from "@/features/documents/viewer/RequisiteNotes";
import type { DocumentStructure } from "@/shared/api/types";
import { Button } from "@/shared/ui/button/Button";
import { SegmentedControl } from "@/shared/ui/segmented/SegmentedControl";

import styles from "./review.module.css";
import { NOTES_MODES, type ReviewState } from "./useReviewState";

/**
 * The margin of the document: findings of the check or the recognised
 * requisites. In a column next to the sheet the findings stand level with
 * their markers; in a drawer they follow one another.
 */
export function NotesPanel({
  state,
  structure,
  handlers,
  layout,
  sheet,
  checked,
  onLocateRequisite,
}: {
  state: ReviewState;
  structure: DocumentStructure;
  handlers: CardHandlers;
  layout: "column" | "drawer";
  sheet: HTMLElement | null;
  /** The check has finished: an empty list means no findings, not "not yet". */
  checked: boolean;
  onLocateRequisite?: () => void;
}) {
  const t = useTranslations();
  const findings = state.mode === "findings";
  const filtered = state.visible.length < state.numbered.length;
  return (
    <div className={styles.notes} data-layout={layout}>
      <div className={styles.notesHead}>
        {/* In a drawer the bottom bar already chose what to show. */}
        {layout === "column" ? (
          <SegmentedControl
            label={t("checks.panelMode")}
            value={state.mode}
            onChange={state.setMode}
            segments={NOTES_MODES.map((mode) => ({
              value: mode,
              label: t(mode === "findings" ? "checks.findingsMode" : "checks.requisitesMode"),
              icon:
                mode === "findings" ? <IconListCheck stroke={1.75} /> : <IconQuote stroke={1.75} />,
            }))}
          />
        ) : null}
        {findings && state.numbered.length > 0 ? (
          <FindingFilters
            filters={state.filters}
            counts={state.counts}
            onChange={state.setFilters}
          />
        ) : null}
      </div>

      {findings ? (
        <>
          {state.general.length > 0 ? (
            <section className={styles.group} aria-label={t("checks.documentWide")}>
              <h2 className={styles.groupTitle}>{t("checks.documentWide")}</h2>
              <FindingList items={state.general} checks={state.checks} handlers={handlers} />
            </section>
          ) : null}
          {state.located.length > 0 ? (
            layout === "column" ? (
              <SidenoteColumn
                items={state.located}
                checks={state.checks}
                handlers={handlers}
                sheet={sheet}
              />
            ) : (
              <FindingList items={state.located} checks={state.checks} handlers={handlers} />
            )
          ) : null}
          {state.visible.length === 0 && checked ? (
            <div className={styles.empty} role="status">
              <p className={styles.emptyTitle}>
                {filtered ? t("checks.noneMatchTitle") : t("checks.noFindingsTitle")}
              </p>
              <p>
                {filtered ? t("checks.noneMatchDescription") : t("checks.noFindingsDescription")}
              </p>
              {filtered ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => state.setFilters(DEFAULT_FILTERS)}
                >
                  {t("checks.resetFilters")}
                </Button>
              ) : null}
            </div>
          ) : null}
        </>
      ) : (
        <>
          <RequisiteNotes notes={state.requisites} onLocate={onLocateRequisite} />
          <section className={styles.group}>
            <h2 className={styles.groupTitle}>{t("viewer.details")}</h2>
            <FileDetails structure={structure} />
          </section>
        </>
      )}
    </div>
  );
}
