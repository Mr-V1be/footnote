import { describe, expect, it } from "vitest";

import { typeset, typesetRuns } from "./typeset";

const NBSP = "\u00a0";

/** Visible form: no-break spaces as «_», unbreakable runs in brackets. */
function show(text: string): string {
  return typesetRuns(typeset(text))
    .map((run) => (run.keep ? `[${run.text}]` : run.text))
    .join("")
    .replaceAll(NBSP, "_");
}

describe("typeset", () => {
  it("keeps document numbers whole, including the hyphen", () => {
    expect(show("приказом от 20.02.2026 № 12-ОД")).toBe("приказом от 20.02.2026 [№_12-ОД]");
    expect(show("Договор № 15/2026")).toBe("Договор [№_15/2026]");
  });

  it("keeps a chain of norm units and the law number together", () => {
    expect(show("согласно п. 2 ч. 1 ст. 18.1 152-ФЗ оператор")).toBe(
      "согласно [п._2_ч._1_ст._18.1_152-ФЗ] оператор",
    );
    expect(show("Федеральным законом № 152-ФЗ")).toBe("Федеральным законом [№_152-ФЗ]");
  });

  it("keeps dates, initials and places on one line", () => {
    expect(show("«03» февраля 2026 г.")).toBe("«03»_февраля_2026_г.");
    expect(show("А.С. Ковалёва")).toBe("А.С._Ковалёва");
    expect(show("г. Москва")).toBe("г._Москва");
  });

  it("binds short words and dashes to their neighbours", () => {
    expect(show("в целях выполнения")).toBe("в_целях выполнения");
    expect(show("(далее — Оператор)")).toBe("(далее_— Оператор)");
  });

  it("preserves the length so offsets into the text stay valid", () => {
    const text = "Приказ № 7-ОД от 14.01.2026 г. Москва";
    expect(typeset(text).text).toHaveLength(text.length);
  });

  it("renders a slice that cuts through an unbreakable span", () => {
    const value = typeset("от 14.01.2026 № 7-ОД");
    const runs = typesetRuns(value, 16, value.text.length);
    expect(runs).toEqual([{ text: "7-ОД", keep: true }]);
  });
});
