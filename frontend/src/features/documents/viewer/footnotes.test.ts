import { describe, expect, it } from "vitest";

import { segmentText, type Footnote } from "./footnotes";

function note(number: number, start: number, end: number): Footnote {
  return { number, blockOrdinal: 0, start, end, tone: "advice", label: `${number}` };
}

describe("segmentText", () => {
  it("splits a block into plain runs and marked spans", () => {
    const segments = segmentText(20, [note(2, 12, 15), note(1, 0, 4)]);
    expect(segments.map(({ type, start, end }) => [type, start, end])).toEqual([
      ["mark", 0, 4],
      ["text", 4, 12],
      ["mark", 12, 15],
      ["text", 15, 20],
    ]);
  });

  it("leaves overlapping and out-of-range spans unmarked", () => {
    const segments = segmentText(10, [note(1, 0, 6), note(2, 3, 8), note(3, 8, 14)]);
    expect(segments.map(({ type, start, end }) => [type, start, end])).toEqual([
      ["mark", 0, 6],
      ["text", 6, 10],
    ]);
  });
});
