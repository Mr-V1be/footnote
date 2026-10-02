"use client";

import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";

import {
  DEFAULT_FILTERS,
  matches,
  numberFindings,
  severityCounts,
  tally,
  type FindingFilters,
  type NumberedFinding,
} from "@/features/checks/findings";
import { requisiteNotes } from "@/features/documents/viewer/requisites";
import type { CheckReport, DocumentStructure } from "@/shared/api/types";

/** What the margin shows: the check's findings or the recognised requisites. */
export type NotesMode = "findings" | "requisites";
export const NOTES_MODES: readonly NotesMode[] = ["findings", "requisites"];

/**
 * Everything the review screen derives from the report and the structure:
 * numbered findings, what the filters let through, the footnotes in the
 * text for the current mode, and the selection shared by text and margin.
 */
export function useReviewState(structure: DocumentStructure, report: CheckReport | null) {
  const t = useTranslations();
  const [mode, setMode] = useState<NotesMode>("findings");
  const [filters, setFilters] = useState<FindingFilters>(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const findings = useMemo(() => report?.findings ?? [], [report]);
  const numbered = useMemo(
    () =>
      numberFindings(findings, (finding, number) =>
        t("checks.markerLabel", { number, title: finding.title }),
      ),
    [findings, t],
  );
  const visible = useMemo(
    () => numbered.filter((item) => matches(item.finding, filters)),
    [numbered, filters],
  );
  const requisites = useMemo(
    () =>
      requisiteNotes(structure.requisites, (requisite, number) =>
        t("viewer.footnoteLabel", { number, kind: t(`requisites.${requisite.kind}`) }),
      ),
    [structure.requisites, t],
  );
  const footnotes = useMemo(
    () =>
      mode === "findings"
        ? visible.flatMap((item) => (item.footnote ? [item.footnote] : []))
        : requisites.map((note) => note.footnote),
    [mode, visible, requisites],
  );
  const checks = useMemo(
    () => new Map((report?.checks ?? []).map((check) => [check.code, check])),
    [report],
  );

  const select = useCallback(
    (id: string) => setSelectedId((current) => (current === id ? null : id)),
    [],
  );
  const byNumber = useCallback(
    (number: number): NumberedFinding | undefined =>
      numbered.find((item) => item.footnote?.number === number),
    [numbered],
  );

  return {
    mode,
    setMode,
    filters,
    setFilters,
    selectedId,
    setSelectedId,
    select,
    byNumber,
    numbered,
    visible,
    general: visible.filter((item) => item.footnote === null),
    located: visible.filter((item) => item.footnote !== null),
    requisites,
    footnotes,
    checks,
    counts: severityCounts(findings),
    tally: tally(report?.results ?? []),
    reviews: findings.filter((finding) => finding.kind === "review" && finding.review === "open")
      .length,
  };
}

export type ReviewState = ReturnType<typeof useReviewState>;
