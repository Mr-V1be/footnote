import type { Severity } from "@/shared/api/types";

/** Ink marks requisites; findings carry the colour of their severity. */
export type FootnoteTone = "ink" | Severity;

/** A marked span of the document and the number of its marker. */
export interface Footnote {
  number: number;
  blockOrdinal: number;
  start: number;
  end: number;
  tone: FootnoteTone;
  /** Accessible name of the marker, e.g. "Сноска 3: дата документа". */
  label: string;
}

/** A slice [start, end) of block text: plain, or marked by a footnote. */
export type Segment =
  | { type: "text"; start: number; end: number }
  | { type: "mark"; start: number; end: number; footnote: Footnote };

interface Placed {
  blockOrdinal: number;
  start: number;
}

/** Reading order: by block, then by position in the block. */
export function byReadingOrder(a: Placed, b: Placed): number {
  return a.blockOrdinal - b.blockOrdinal || a.start - b.start;
}

export function footnotesByBlock(footnotes: readonly Footnote[]): Map<number, Footnote[]> {
  const grouped = new Map<number, Footnote[]>();
  for (const footnote of footnotes) {
    const list = grouped.get(footnote.blockOrdinal) ?? [];
    list.push(footnote);
    grouped.set(footnote.blockOrdinal, list);
  }
  return grouped;
}

/**
 * Splits block text into plain runs and marked spans. Overlapping spans are
 * not nested: a span that starts inside the previous one is left unmarked
 * and keeps only its card in the margin.
 */
export function segmentText(length: number, footnotes: readonly Footnote[]): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  for (const footnote of [...footnotes].sort(byReadingOrder)) {
    const { start, end } = footnote;
    if (start < cursor || end > length || start >= end) continue;
    if (start > cursor) segments.push({ type: "text", start: cursor, end: start });
    segments.push({ type: "mark", start, end, footnote });
    cursor = end;
  }
  if (cursor < length) segments.push({ type: "text", start: cursor, end: length });
  return segments;
}

export const anchors = {
  block: (ordinal: number) => `block-${ordinal}`,
  footnote: (number: number) => `footnote-${number}`,
  mark: (number: number) => `mark-${number}`,
};
