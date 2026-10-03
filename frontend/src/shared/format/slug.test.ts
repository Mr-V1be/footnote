import { describe, expect, it } from "vitest";

import { SLUG_PATTERN, slugify } from "./slug";

describe("slugify", () => {
  it("transliterates a Russian name into a valid address", () => {
    expect(slugify("Кадры и персонал")).toBe("kadry-i-personal");
    expect(slugify("Договоры № 2026")).toBe("dogovory-2026");
    expect(SLUG_PATTERN.test(slugify("  Щука — ёлка!  "))).toBe(true);
  });

  it("returns nothing for a name without letters or digits", () => {
    expect(slugify("№ — !")).toBe("");
  });
});
