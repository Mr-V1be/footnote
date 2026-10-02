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

/**
 * A place shown for a while without a marker: where a finding about the
 * document as a whole applies, while that finding is open.
 */
export interface Highlight {
  blockOrdinal: number;
  start: number;
  end: number;
  tone: FootnoteTone;
}

/** What is marked in one block. */
export interface BlockMarks {
  footnotes: readonly Footnote[];
  highlights: readonly Highlight[];
}

export const NO_MARKS: BlockMarks = { footnotes: [], highlights: [] };

/** A slice [start, end) of block text: plain, marked by a footnote, or highlighted. */
export type Segment =
  | { type: "text"; start: number; end: number }
  | { type: "mark"; start: number; end: number; footnote: Footnote }
  | { type: "highlight"; start: number; end: number; tone: FootnoteTone };

interface Placed {
  blockOrdinal: number;
  start: number;
}

/** Reading order: by block, then by position in the block. */
export function byReadingOrder(a: Placed, b: Placed): number {
  return a.blockOrdinal - b.blockOrdinal || a.start - b.start;
}

export function marksByBlock(
  footnotes: readonly Footnote[],
  highlights: readonly Highlight[],
): Map<number, BlockMarks> {
  const grouped = new Map<number, { footnotes: Footnote[]; highlights: Highlight[] }>();
  const entry = (ordinal: number) => {
    const existing = grouped.get(ordinal);
    if (existing) return existing;
    const created = { footnotes: [], highlights: [] };
    grouped.set(ordinal, created);
    return created;
  };
  for (const footnote of footnotes) entry(footnote.blockOrdinal).footnotes.push(footnote);
  for (const highlight of highlights) entry(highlight.blockOrdinal).highlights.push(highlight);
  return grouped;
}

function overlaps(a: { start: number; end: number }, b: { start: number; end: number }): boolean {
  return a.start < b.end && b.start < a.end;
}

/**
 * Splits block text into plain runs, marked spans and highlighted places.
 * Overlapping spans are not nested: a span that starts inside the previous
 * one is left unmarked and keeps only its card in the margin. Footnotes come
 * first: a highlight that would cover a footnote's span is not shown.
 */
export function segmentText(
  length: number,
  footnotes: readonly Footnote[],
  highlights: readonly Highlight[] = [],
): Segment[] {
  const spans = [
    ...footnotes.map((footnote) => ({ ...footnote, footnote })),
    ...highlights
      .filter((highlight) => !footnotes.some((footnote) => overlaps(footnote, highlight)))
      .map((highlight) => ({ ...highlight, footnote: null })),
  ].sort(byReadingOrder);
  const segments: Segment[] = [];
  let cursor = 0;
  for (const span of spans) {
    const { start, end } = span;
    if (start < cursor || end > length || start >= end) continue;
    if (start > cursor) segments.push({ type: "text", start: cursor, end: start });
    segments.push(
      span.footnote
        ? { type: "mark", start, end, footnote: span.footnote }
        : { type: "highlight", start, end, tone: span.tone },
    );
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
