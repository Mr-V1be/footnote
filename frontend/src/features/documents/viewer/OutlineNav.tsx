"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import type { OutlineEntry } from "@/shared/api/types";

import { anchors } from "./footnotes";
import styles from "./panels.module.css";

/** Offset below which a heading counts as the current section. */
const CURRENT_SECTION_OFFSET_PX = 140;

function useCurrentSection(entries: readonly OutlineEntry[]): number | null {
  const [current, setCurrent] = useState<number | null>(entries[0]?.blockOrdinal ?? null);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      let found: number | null = entries[0]?.blockOrdinal ?? null;
      for (const entry of entries) {
        const element = document.getElementById(anchors.block(entry.blockOrdinal));
        if (element && element.getBoundingClientRect().top <= CURRENT_SECTION_OFFSET_PX)
          found = entry.blockOrdinal;
      }
      setCurrent(found);
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", schedule, { passive: true });
    return () => {
      window.removeEventListener("scroll", schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [entries]);
  return current;
}

export function OutlineNav({
  entries,
  pending = false,
  onNavigate,
}: {
  entries: readonly OutlineEntry[];
  /** The version is still being parsed: nothing is known yet. */
  pending?: boolean;
  onNavigate?: () => void;
}) {
  const t = useTranslations("viewer");
  const current = useCurrentSection(entries);
  if (entries.length === 0) {
    return <p className={styles.empty}>{t(pending ? "afterParsing" : "noOutline")}</p>;
  }
  return (
    <nav aria-label={t("outline")}>
      <ol className={styles.outline}>
        {entries.map((entry) => (
          <li key={entry.blockOrdinal} data-level={Math.min(entry.level, 3)}>
            <a
              href={`#${anchors.block(entry.blockOrdinal)}`}
              className={`${styles.outlineLink} ${current === entry.blockOrdinal ? styles.outlineCurrent : ""}`}
              aria-current={current === entry.blockOrdinal ? "location" : undefined}
              onClick={(event) => {
                event.preventDefault();
                onNavigate?.();
                window.requestAnimationFrame(() =>
                  document
                    .getElementById(anchors.block(entry.blockOrdinal))
                    ?.scrollIntoView({ block: "start" }),
                );
              }}
            >
              {entry.label ? <span className={styles.outlineLabel}>{entry.label}</span> : null}
              <span className={styles.outlineText}>{entry.text}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
