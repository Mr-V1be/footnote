"use client";

import { IconCrosshair } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { useFootnotes } from "./FootnoteContext";
import { anchors, type Footnote } from "./footnotes";
import styles from "./panels.module.css";
import { Typeset } from "@/shared/typography/Typeset";

/** Margin notes: one card per marker in the text. */
export function FootnoteList({
  footnotes,
  pending = false,
  onLocate,
}: {
  footnotes: readonly Footnote[];
  /** The version is still being parsed: nothing is known yet. */
  pending?: boolean;
  onLocate?: () => void;
}) {
  const t = useTranslations();
  const { active, setActive, revealMark } = useFootnotes();
  if (footnotes.length === 0) {
    return (
      <p className={styles.empty}>{t(pending ? "viewer.afterParsing" : "viewer.noRequisites")}</p>
    );
  }
  return (
    <ol className={styles.footnotes} aria-label={t("viewer.footnotes")}>
      {footnotes.map(({ number, requisite }) => (
        <li
          key={number}
          id={anchors.footnote(number)}
          className={`${styles.footnote} ${active === number ? styles.footnoteActive : ""}`}
          onMouseEnter={() => setActive(number)}
          onMouseLeave={() => setActive(null)}
        >
          <span className={styles.footnoteNumber} aria-hidden>
            {number}
          </span>
          <div className={styles.footnoteBody}>
            <span className={styles.footnoteKind}>{t(`requisites.${requisite.kind}`)}</span>
            <span className={styles.footnoteValue}>
              <Typeset text={requisite.value} />
            </span>
          </div>
          <button
            type="button"
            className={styles.locate}
            aria-label={`${t("viewer.showInText")}: ${t(`requisites.${requisite.kind}`)}`}
            title={t("viewer.showInText")}
            onClick={() => {
              onLocate?.();
              window.requestAnimationFrame(() => revealMark(number));
            }}
            onFocus={() => setActive(number)}
            onBlur={() => setActive(null)}
          >
            <IconCrosshair stroke={1.75} aria-hidden />
          </button>
        </li>
      ))}
    </ol>
  );
}
