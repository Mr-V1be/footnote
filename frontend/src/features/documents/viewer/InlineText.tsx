"use client";

import { useTranslations } from "next-intl";

import { useFootnotes } from "./FootnoteContext";
import { anchors, segmentText, type Footnote } from "./footnotes";
import styles from "./sheet.module.css";

/** Block text with requisite spans marked and their footnote markers. */
export function InlineText({ text, footnotes }: { text: string; footnotes: readonly Footnote[] }) {
  const t = useTranslations();
  const { active, setActive, revealCard } = useFootnotes();
  if (footnotes.length === 0) return <>{text}</>;
  return (
    <>
      {segmentText(text, footnotes).map((segment, index) => {
        if (segment.type === "text") return <span key={index}>{segment.text}</span>;
        const { number, requisite } = segment.footnote;
        const isActive = active === number;
        return (
          <span key={index} className={styles.marked}>
            <mark
              id={anchors.mark(number)}
              className={`${styles.mark} ${isActive ? styles.markActive : ""}`}
              onMouseEnter={() => setActive(number)}
              onMouseLeave={() => setActive(null)}
            >
              {segment.text}
            </mark>
            {/* A word joiner keeps the marker on the line of the text it annotates. */}
            {"\u2060"}
            <sup className={styles.marker}>
              <a
                href={`#${anchors.footnote(number)}`}
                aria-label={t("viewer.footnoteLabel", {
                  number,
                  kind: t(`requisites.${requisite.kind}`),
                })}
                onClick={(event) => {
                  event.preventDefault();
                  revealCard(number);
                }}
                onFocus={() => setActive(number)}
                onBlur={() => setActive(null)}
              >
                {number}
              </a>
            </sup>
          </span>
        );
      })}
    </>
  );
}
