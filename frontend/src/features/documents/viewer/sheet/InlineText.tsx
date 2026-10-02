"use client";

import { useMemo } from "react";

import { TypesetRuns } from "@/shared/typography/Typeset";
import { typeset } from "@/shared/typography/typeset";

import { useFootnotes } from "../FootnoteContext";
import { anchors, segmentText, type Footnote } from "../footnotes";
import styles from "./sheet.module.css";

/**
 * Block text with requisite spans marked and their footnote markers. The
 * text is typeset once as a whole, so a number or a date stays unbroken even
 * where a mark begins in the middle of it.
 */
export function InlineText({ text, footnotes }: { text: string; footnotes: readonly Footnote[] }) {
  const { active, setActive, revealCard } = useFootnotes();
  const value = useMemo(() => typeset(text), [text]);
  if (footnotes.length === 0) return <TypesetRuns value={value} />;
  return (
    <>
      {segmentText(value.text.length, footnotes).map((segment, index) => {
        if (segment.type === "text") {
          return (
            <span key={index}>
              <TypesetRuns value={value} start={segment.start} end={segment.end} />
            </span>
          );
        }
        const { number, tone, label } = segment.footnote;
        const isActive = active === number;
        return (
          <span key={index} className={styles.marked}>
            <mark
              id={anchors.mark(number)}
              data-tone={tone}
              className={`${styles.mark} ${isActive ? styles.markActive : ""}`}
              onMouseEnter={() => setActive(number)}
              onMouseLeave={() => setActive(null)}
            >
              <TypesetRuns value={value} start={segment.start} end={segment.end} />
            </mark>
            {/* A word joiner keeps the marker on the line of the text it annotates. */}
            {"\u2060"}
            <sup className={styles.marker}>
              <a
                href={`#${anchors.footnote(number)}`}
                aria-label={label}
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
