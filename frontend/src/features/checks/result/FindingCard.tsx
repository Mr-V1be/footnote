"use client";

import { IconCrosshair, IconFileDescription } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState, type Ref } from "react";

import { anchors } from "@/features/documents/viewer/footnotes";
import type { CheckDefinition, Finding, ReviewStatus } from "@/shared/api/types";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Typeset } from "@/shared/typography/Typeset";

import type { NumberedFinding } from "../findings";
import styles from "./finding-card.module.css";
import { ReviewActions } from "./ReviewActions";
import { useFindingText } from "./useFindingText";

/** Lines of a provision shown before "show more". */
const QUOTE_PREVIEW_CHARS = 280;

function Norm({ finding, check }: { finding: Finding; check: CheckDefinition | undefined }) {
  const t = useTranslations("checks");
  const [full, setFull] = useState(false);
  const quote = finding.norm.quote;
  if (!quote) {
    // A standard is not quoted: the check states the rule in its own words.
    return (
      <figure className={styles.norm}>
        <figcaption className={styles.normLabel}>{t("requirement")}</figcaption>
        {check ? <p className={styles.requirement}>{check.requirement}</p> : null}
        <p className={styles.citation}>
          <Typeset text={finding.norm.citation} />
        </p>
      </figure>
    );
  }
  const long = quote.length > QUOTE_PREVIEW_CHARS;
  const shown = long && !full ? `${quote.slice(0, QUOTE_PREVIEW_CHARS).trimEnd()}…` : quote;
  return (
    <figure className={styles.norm}>
      <figcaption className={styles.normLabel}>{t("norm")}</figcaption>
      <blockquote className={styles.quote} lang="ru">
        <Typeset text={shown} />
      </blockquote>
      <p className={styles.citation}>
        <Typeset text={finding.norm.citation} />
      </p>
      {long ? (
        <button type="button" className={styles.more} onClick={() => setFull((value) => !value)}>
          {full ? t("showLess") : t("showMore")}
        </button>
      ) : null}
    </figure>
  );
}

/**
 * A footnote on the document: what is wrong, the norm it rests on and how to
 * fix it, with the team's decision. Collapsed it shows only what is needed
 * to recognise it; selecting it opens the rest.
 */
export function FindingCard({
  item,
  check,
  expanded,
  active,
  busy,
  onSelect,
  onReview,
  onLocate,
  cardRef,
}: {
  item: NumberedFinding;
  check: CheckDefinition | undefined;
  expanded: boolean;
  active: boolean;
  busy: boolean;
  onSelect: () => void;
  onReview: (review: ReviewStatus) => void;
  onLocate?: () => void;
  cardRef?: Ref<HTMLElement>;
}) {
  const t = useTranslations("checks");
  const familyLabel = useCodeLabel("familiesShort");
  const text = useFindingText();
  const { finding, footnote } = item;
  const id = footnote ? anchors.footnote(footnote.number) : `finding-${finding.id}`;
  const family = check ? familyLabel(check.family) : null;
  const method = check ? t(`method.${check.method}`) : null;
  return (
    <article
      ref={cardRef}
      id={id}
      className={styles.card}
      data-severity={finding.severity}
      data-active={active || undefined}
      data-resolved={finding.review === "rejected" || finding.review === "fixed" || undefined}
      aria-labelledby={`${id}-title`}
    >
      <header className={styles.head}>
        <span className={styles.marker} aria-hidden>
          {footnote ? footnote.number : <IconFileDescription stroke={1.75} />}
        </span>
        <span className={styles.severity}>{t(`severity.${finding.severity}`)}</span>
        {finding.kind === "review" ? (
          <span className={styles.lawyer}>{t("kind.review")}</span>
        ) : null}
        {family ? (
          <span className={styles.source}>
            {family}, {method}
          </span>
        ) : null}
      </header>
      <button
        type="button"
        className={styles.summary}
        aria-expanded={expanded}
        aria-controls={`${id}-body`}
        onClick={onSelect}
      >
        <h3 className={styles.title} id={`${id}-title`}>
          <Typeset text={finding.title} />
        </h3>
        <p className={styles.detail} data-clamped={!expanded || undefined}>
          <Typeset text={text(finding.detail)} />
        </p>
      </button>
      {expanded ? (
        <div className={styles.body} id={`${id}-body`}>
          <Norm finding={finding} check={check} />
          {finding.kind === "violation" ? (
            <section className={styles.fix}>
              <h4 className={styles.fixLabel}>{t("howToFix")}</h4>
              <p>
                <Typeset text={finding.recommendation} />
              </p>
            </section>
          ) : null}
          <footer className={styles.foot}>
            <ReviewActions finding={finding} busy={busy} onReview={onReview} />
            {footnote && onLocate ? (
              <button type="button" className={styles.locate} onClick={onLocate}>
                <IconCrosshair stroke={1.75} aria-hidden />
                {t("showInText")}
              </button>
            ) : null}
          </footer>
        </div>
      ) : null}
    </article>
  );
}
