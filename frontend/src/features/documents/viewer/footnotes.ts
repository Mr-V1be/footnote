import type { Requisite } from "@/shared/api/types";

export interface Footnote {
  number: number;
  requisite: Requisite;
}

export type Segment =
  { type: "text"; text: string } | { type: "mark"; text: string; footnote: Footnote };

/** Footnotes are numbered in reading order, as markers appear in the text. */
export function numberFootnotes(requisites: readonly Requisite[]): Footnote[] {
  return [...requisites]
    .sort((a, b) => a.blockOrdinal - b.blockOrdinal || a.start - b.start)
    .map((requisite, index) => ({ number: index + 1, requisite }));
}

export function footnotesByBlock(footnotes: readonly Footnote[]): Map<number, Footnote[]> {
  const grouped = new Map<number, Footnote[]>();
  for (const footnote of footnotes) {
    const list = grouped.get(footnote.requisite.blockOrdinal) ?? [];
    list.push(footnote);
    grouped.set(footnote.requisite.blockOrdinal, list);
  }
  return grouped;
}

/**
 * Splits block text into plain runs and marked spans. Overlapping spans are
 * not nested: a span that starts inside the previous one is left unmarked
 * and keeps only its card in the margin.
 */
export function segmentText(text: string, footnotes: readonly Footnote[]): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  for (const footnote of footnotes) {
    const { start, end } = footnote.requisite;
    if (start < cursor || end > text.length || start >= end) continue;
    if (start > cursor) segments.push({ type: "text", text: text.slice(cursor, start) });
    segments.push({ type: "mark", text: text.slice(start, end), footnote });
    cursor = end;
  }
  if (cursor < text.length) segments.push({ type: "text", text: text.slice(cursor) });
  return segments;
}

export const anchors = {
  block: (ordinal: number) => `block-${ordinal}`,
  footnote: (number: number) => `footnote-${number}`,
  mark: (number: number) => `mark-${number}`,
};
