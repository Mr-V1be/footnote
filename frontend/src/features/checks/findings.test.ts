import { describe, expect, it } from "vitest";

import type { CheckResult, Finding } from "@/shared/api/types";

import { DEFAULT_FILTERS, matches, numberFindings, severityCounts, tally } from "./findings";

let sequence = 0;

function finding(overrides: Partial<Finding>): Finding {
  sequence += 1;
  return {
    id: `f-${sequence}`,
    checkCode: "formatting.date_format",
    kind: "violation",
    severity: "advice",
    title: "Дата записана не по стандарту",
    detail: { code: "date_format", params: { value: "1.2.2026" }, text: null },
    recommendation: "",
    norm: { citation: "п. 5.10 ГОСТ Р 7.0.97-2016", actCode: null, anchor: null, quote: null },
    location: null,
    review: "open",
    reviewedAt: null,
    revision: 1,
    ...overrides,
  };
}

const label = (_: Finding, number: number) => `Замечание ${number}`;

describe("numberFindings", () => {
  it("numbers located findings in reading order after the document-wide ones", () => {
    const later = finding({ location: { blockOrdinal: 4, start: 10, end: 20 } });
    const earlier = finding({ location: { blockOrdinal: 4, start: 0, end: 5 } });
    const advice = finding({ severity: "advice" });
    const critical = finding({ severity: "critical" });
    const numbered = numberFindings([later, advice, earlier, critical], label);
    expect(numbered.map((item) => item.finding.id)).toEqual([
      critical.id,
      advice.id,
      earlier.id,
      later.id,
    ]);
    expect(numbered.map((item) => item.footnote?.number ?? null)).toEqual([null, null, 1, 2]);
    expect(numbered[2]?.footnote?.label).toBe("Замечание 1");
  });
});

describe("filters", () => {
  it("shows outstanding findings by default and resolved ones on request", () => {
    const open = finding({ review: "open" });
    const accepted = finding({ review: "accepted" });
    const fixed = finding({ review: "fixed" });
    expect([open, accepted, fixed].map((item) => matches(item, DEFAULT_FILTERS))).toEqual([
      true,
      true,
      false,
    ]);
    const resolved = { ...DEFAULT_FILTERS, scope: "resolved" as const };
    expect(matches(fixed, resolved)).toBe(true);
    expect(matches(finding({ severity: "critical" }), { ...DEFAULT_FILTERS, severities: [] })).toBe(
      false,
    );
  });

  it("counts outstanding violations by severity, not reviews or fixed ones", () => {
    const counts = severityCounts([
      finding({ severity: "critical" }),
      finding({ severity: "critical", review: "fixed" }),
      finding({ severity: "important", kind: "review" }),
      finding({ severity: "advice", review: "accepted" }),
    ]);
    expect(counts).toEqual({ critical: 1, important: 0, advice: 1 });
  });
});

describe("tally", () => {
  it("tells checks without a connected model apart from other errors", () => {
    const result = (status: CheckResult["status"], errorCode: string | null = null) =>
      ({ status, errorCode }) as CheckResult;
    expect(
      tally([
        result("passed"),
        result("violation"),
        result("needs_review"),
        result("not_applicable"),
        result("error", "model_not_configured"),
        result("error", "invalid_model_answer"),
      ]),
    ).toEqual({
      passed: 1,
      violations: 1,
      reviews: 1,
      notApplicable: 1,
      notPerformed: 2,
      modelMissing: 1,
    });
  });
});
