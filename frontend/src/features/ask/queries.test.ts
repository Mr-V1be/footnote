import { describe, expect, it } from "vitest";

import { answerParts } from "./queries";

describe("answerParts", () => {
  it("splits an answer into text and footnote markers", () => {
    expect(answerParts("Согласие отзывается [1], оператор прекращает обработку [2].")).toEqual([
      { type: "text", text: "Согласие отзывается" },
      { type: "marker", number: 1 },
      { type: "text", text: ", оператор прекращает обработку" },
      { type: "marker", number: 2 },
      { type: "text", text: "." },
    ]);
  });

  it("keeps an answer without markers whole", () => {
    expect(answerParts("Без сносок.")).toEqual([{ type: "text", text: "Без сносок." }]);
  });
});
