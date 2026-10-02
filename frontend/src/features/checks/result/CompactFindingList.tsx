"use client";

import { useTranslations } from "next-intl";
import { VisuallyHidden } from "radix-ui";

import type { CheckDefinition } from "@/shared/api/types";
import { Typeset } from "@/shared/typography/Typeset";

import type { NumberedFinding } from "../findings";
import { FindingCard } from "./FindingCard";
import type { CardHandlers } from "./FindingList";
import styles from "./result.module.css";

/**
 * Findings one line each, the selected one open in full. Used in the margin
 * for findings about the document as a whole, so they leave the room level
 * with the text to the notes that point into it.
 */
export function CompactFindingList({
  items,
  checks,
  handlers,
}: {
  items: readonly NumberedFinding[];
  checks: ReadonlyMap<string, CheckDefinition>;
  handlers: CardHandlers;
}) {
  const t = useTranslations("checks");
  return (
    <ol className={styles.compact}>
      {items.map((item) => {
        const { finding } = item;
        if (handlers.selectedId === finding.id) {
          return (
            <li key={finding.id} className={styles.compactOpen}>
              <FindingCard
                item={item}
                check={checks.get(finding.checkCode)}
                expanded
                active
                busy={handlers.busyId === finding.id}
                onSelect={() => handlers.onSelect(finding.id)}
                onReview={(review) => handlers.onReview(item, review)}
              />
            </li>
          );
        }
        return (
          <li key={finding.id}>
            <button
              type="button"
              className={styles.compactRow}
              data-severity={finding.severity}
              data-resolved={
                finding.review === "rejected" || finding.review === "fixed" || undefined
              }
              onClick={() => handlers.onSelect(finding.id)}
            >
              <span className={styles.compactDot} aria-hidden />
              <VisuallyHidden.Root>{t(`severity.${finding.severity}`)}: </VisuallyHidden.Root>
              <span className={styles.compactTitle}>
                <Typeset text={finding.title} />
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
