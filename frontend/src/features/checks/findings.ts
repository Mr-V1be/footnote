import { byReadingOrder, type Footnote } from "@/features/documents/viewer/footnotes";
import type { CheckResult, Finding, ReviewStatus, Severity } from "@/shared/api/types";

export const SEVERITIES: readonly Severity[] = ["critical", "important", "advice"];
export const REVIEW_STATUSES: readonly ReviewStatus[] = ["accepted", "rejected", "fixed"];

/** Which findings a reader is looking at, by what was decided about them. */
export const REVIEW_SCOPES = ["outstanding", "resolved", "all"] as const;
export type ReviewScope = (typeof REVIEW_SCOPES)[number];

const OUTSTANDING: readonly ReviewStatus[] = ["open", "accepted"];

export interface FindingFilters {
  severities: readonly Severity[];
  scope: ReviewScope;
}

export const DEFAULT_FILTERS: FindingFilters = { severities: SEVERITIES, scope: "outstanding" };

export function isOutstanding(finding: Finding): boolean {
  return OUTSTANDING.includes(finding.review);
}

function inScope(finding: Finding, scope: ReviewScope): boolean {
  if (scope === "all") return true;
  return scope === "outstanding" ? isOutstanding(finding) : !isOutstanding(finding);
}

export function matches(finding: Finding, filters: FindingFilters): boolean {
  return filters.severities.includes(finding.severity) && inScope(finding, filters.scope);
}

/** A finding with its marker in the text; findings about the whole document have none. */
export interface NumberedFinding {
  finding: Finding;
  footnote: Footnote | null;
}

/**
 * Located findings are numbered in reading order over the whole run, so a
 * marker keeps its number whatever the filters show. Findings about the
 * document as a whole come first, the most serious first.
 */
export function numberFindings(
  findings: readonly Finding[],
  label: (finding: Finding, number: number) => string,
): NumberedFinding[] {
  const general = findings
    .filter((finding) => finding.location === null)
    .sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity));
  const located = findings
    .flatMap((finding) => (finding.location ? [{ finding, ...finding.location }] : []))
    .sort(byReadingOrder);
  return [
    ...general.map((finding) => ({ finding, footnote: null })),
    ...located.map(({ finding, blockOrdinal, start, end }, index) => ({
      finding,
      footnote: {
        number: index + 1,
        blockOrdinal,
        start,
        end,
        tone: finding.severity,
        label: label(finding, index + 1),
      },
    })),
  ];
}

export function severityCounts(findings: readonly Finding[]): Record<Severity, number> {
  const counts: Record<Severity, number> = { critical: 0, important: 0, advice: 0 };
  for (const finding of findings) {
    if (finding.kind === "violation" && isOutstanding(finding)) counts[finding.severity] += 1;
  }
  return counts;
}

/** Outcome of the run in numbers the summary shows. */
export interface RunTally {
  passed: number;
  violations: number;
  reviews: number;
  notApplicable: number;
  notPerformed: number;
  /** Model checks skipped because no model API is configured. */
  modelMissing: number;
}

const MODEL_NOT_CONFIGURED = "model_not_configured";

export function tally(results: readonly CheckResult[]): RunTally {
  const count = (status: CheckResult["status"]) =>
    results.filter((result) => result.status === status).length;
  return {
    passed: count("passed"),
    violations: count("violation"),
    reviews: count("needs_review"),
    notApplicable: count("not_applicable"),
    notPerformed: count("error"),
    modelMissing: results.filter((result) => result.errorCode === MODEL_NOT_CONFIGURED).length,
  };
}
