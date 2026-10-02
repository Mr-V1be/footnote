import { TYPOGRAPHIC_RULES, type TypographicRule } from "./rules";

export interface TextRange {
  readonly start: number;
  readonly end: number;
}

/**
 * Text prepared for display. Spaces inside protected spans are no-break
 * spaces, so the text keeps its length and offsets into it stay valid.
 * `keep` lists the spans that also contain a hyphen or a slash, where the
 * browser would otherwise break; they are rendered as unbreakable runs.
 */
export interface TypesetText {
  readonly text: string;
  readonly keep: readonly TextRange[];
}

export interface TypesetRun {
  readonly text: string;
  readonly keep: boolean;
}

const NO_BREAK_SPACE = "\u00a0";
const SPACE = " ";
const BREAKABLE_PUNCTUATION = /[-\u2010\u2013/]/u;

function mergeRanges(ranges: TextRange[]): TextRange[] {
  const sorted = ranges.toSorted((a, b) => a.start - b.start || a.end - b.end);
  const merged: TextRange[] = [];
  for (const range of sorted) {
    const last = merged.at(-1);
    if (last && range.start <= last.end) {
      merged[merged.length - 1] = { start: last.start, end: Math.max(last.end, range.end) };
    } else {
      merged.push(range);
    }
  }
  return merged;
}

export function typeset(
  text: string,
  rules: readonly TypographicRule[] = TYPOGRAPHIC_RULES,
): TypesetText {
  const characters = text.split("");
  const keep: TextRange[] = [];
  for (const { pattern } of rules) {
    for (const match of text.matchAll(pattern)) {
      const start = match.index;
      const end = start + match[0].length;
      for (let index = start; index < end; index += 1) {
        if (characters[index] === SPACE) characters[index] = NO_BREAK_SPACE;
      }
      if (BREAKABLE_PUNCTUATION.test(match[0])) keep.push({ start, end });
    }
  }
  return { text: characters.join(""), keep: mergeRanges(keep) };
}

/** Runs of the slice [start, end): plain text and spans that must not break. */
export function typesetRuns(value: TypesetText, start = 0, end = value.text.length): TypesetRun[] {
  const runs: TypesetRun[] = [];
  let cursor = start;
  for (const range of value.keep) {
    if (range.end <= start || range.start >= end) continue;
    const from = Math.max(range.start, start);
    const to = Math.min(range.end, end);
    if (from > cursor) runs.push({ text: value.text.slice(cursor, from), keep: false });
    runs.push({ text: value.text.slice(from, to), keep: true });
    cursor = to;
  }
  if (cursor < end) runs.push({ text: value.text.slice(cursor, end), keep: false });
  return runs;
}
