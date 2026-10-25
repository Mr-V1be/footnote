import { describe, expect, it } from "vitest";

import { preferredLocale, resolveLocale } from "./negotiation";

describe("resolveLocale", () => {
  it("takes the stored choice over the browser's language", () => {
    expect(resolveLocale({ stored: "ru", acceptLanguage: "en-US,en;q=0.9" })).toBe("ru");
    expect(resolveLocale({ stored: "en", acceptLanguage: "ru-RU,ru;q=0.9" })).toBe("en");
  });

  it("follows the browser when nothing usable is stored", () => {
    expect(resolveLocale({ stored: undefined, acceptLanguage: "ru-RU,ru;q=0.9,en;q=0.8" })).toBe(
      "ru",
    );
    expect(resolveLocale({ stored: "de", acceptLanguage: "ru" })).toBe("ru");
  });

  it("falls back to English", () => {
    expect(resolveLocale({ stored: undefined, acceptLanguage: "de-DE,fr;q=0.8" })).toBe("en");
    expect(resolveLocale({ stored: null, acceptLanguage: null })).toBe("en");
  });
});

describe("preferredLocale", () => {
  it("picks the supported language with the highest weight, then the first listed", () => {
    expect(preferredLocale("de-DE,de;q=0.9,ru;q=0.6,en;q=0.7")).toBe("en");
    expect(preferredLocale("ru;q=0.4, en;q=0.8")).toBe("en");
    expect(preferredLocale("en, ru")).toBe("en");
    expect(preferredLocale("ru_RU")).toBe("ru");
  });

  it("ignores languages refused with a zero weight and wildcards", () => {
    expect(preferredLocale("en;q=0, ru;q=0.5")).toBe("ru");
    expect(preferredLocale("*")).toBeNull();
    expect(preferredLocale("")).toBeNull();
  });
});
