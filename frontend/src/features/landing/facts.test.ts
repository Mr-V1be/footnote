import { describe, expect, it } from "vitest";

import type { CheckCatalog } from "@/shared/api/types";

import { mostChecksPerDocument } from "./facts";

function catalog(kinds: string[][]): CheckCatalog {
  return {
    checks: kinds.map((list, index) => ({ code: `c${index}`, kinds: list })),
  } as unknown as CheckCatalog;
}

describe("mostChecksPerDocument", () => {
  it("counts the checks of the kind that gets the most, not the catalog", () => {
    expect(mostChecksPerDocument(catalog([["policy", "order"], ["policy"], ["order"]]))).toBe(2);
  });

  it("is zero for an empty catalog", () => {
    expect(mostChecksPerDocument(catalog([]))).toBe(0);
  });
});
