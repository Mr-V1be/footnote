"use client";

import type { CheckDefinition, ReviewStatus } from "@/shared/api/types";

import type { NumberedFinding } from "../findings";
import { FindingCard } from "./FindingCard";
import styles from "./result.module.css";

export interface CardHandlers {
  selectedId: string | null;
  busyId: string | null;
  onSelect: (id: string) => void;
  onReview: (item: NumberedFinding, review: ReviewStatus) => void;
  onLocate: (item: NumberedFinding) => void;
  onHover: (number: number | null) => void;
  activeNumber: number | null;
}

/** Findings one under another, in the order given. */
export function FindingList({
  items,
  checks,
  handlers,
}: {
  items: readonly NumberedFinding[];
  checks: ReadonlyMap<string, CheckDefinition>;
  handlers: CardHandlers;
}) {
  return (
    <ol className={styles.stack}>
      {items.map((item) => (
        <li
          key={item.finding.id}
          onMouseEnter={() => handlers.onHover(item.footnote?.number ?? null)}
          onMouseLeave={() => handlers.onHover(null)}
        >
          <FindingCard
            item={item}
            check={checks.get(item.finding.checkCode)}
            expanded={handlers.selectedId === item.finding.id}
            active={
              handlers.selectedId === item.finding.id ||
              (item.footnote !== null && handlers.activeNumber === item.footnote.number)
            }
            busy={handlers.busyId === item.finding.id}
            onSelect={() => handlers.onSelect(item.finding.id)}
            onReview={(review) => handlers.onReview(item, review)}
            onLocate={item.footnote ? () => handlers.onLocate(item) : undefined}
          />
        </li>
      ))}
    </ol>
  );
}
