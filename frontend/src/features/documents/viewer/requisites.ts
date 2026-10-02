import type { Requisite } from "@/shared/api/types";

import { byReadingOrder, type Footnote } from "./footnotes";

export interface RequisiteNote {
  footnote: Footnote;
  requisite: Requisite;
}

/** Requisites numbered in reading order, as their markers appear in the text. */
export function requisiteNotes(
  requisites: readonly Requisite[],
  label: (requisite: Requisite, number: number) => string,
): RequisiteNote[] {
  return [...requisites].sort(byReadingOrder).map((requisite, index) => ({
    requisite,
    footnote: {
      number: index + 1,
      blockOrdinal: requisite.blockOrdinal,
      start: requisite.start,
      end: requisite.end,
      tone: "ink",
      label: label(requisite, index + 1),
    },
  }));
}
