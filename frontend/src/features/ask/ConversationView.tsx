"use client";

import { IconSearchOff } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import type { ConversationTurn } from "@/shared/api/types";
import { Typeset } from "@/shared/typography/Typeset";
import { Notice } from "@/shared/ui/notice/Notice";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";

import styles from "./ask.module.css";
import { answerParts } from "./queries";

/** The questions of a conversation and their answers, oldest first. */
export function ConversationView({
  turns,
  pendingQuestion,
}: {
  turns: readonly ConversationTurn[];
  /** A question on its way: shown at once, its answer as a placeholder. */
  pendingQuestion: string | null;
}) {
  const t = useTranslations("ask");
  return (
    <div className={styles.turns}>
      {turns.map((turn) => (
        <article key={turn.id} className={styles.turn} aria-label={turn.question}>
          <p className={styles.question}>{turn.question}</p>
          {turn.status === "answered" && turn.answer ? (
            <Answer turn={turn} />
          ) : (
            <Notice icon={<IconSearchOff stroke={1.75} />} title={t("notFoundTitle")}>
              {t("notFoundDescription")}
            </Notice>
          )}
        </article>
      ))}
      {pendingQuestion ? (
        <article className={styles.turn} aria-busy>
          <p className={styles.question}>{pendingQuestion}</p>
          <div className={styles.pending} role="status">
            <span className={styles.pendingLabel}>{t("searching")}</span>
            <Skeleton width="92%" />
            <Skeleton width="78%" />
            <Skeleton width="60%" />
          </div>
        </article>
      ) : null}
    </div>
  );
}

function Answer({ turn }: { turn: ConversationTurn }) {
  const t = useTranslations("ask");
  const anchor = (number: number) => `cite-${turn.id}-${number}`;
  return (
    <div className={styles.answer}>
      <p className={styles.answerText}>
        {answerParts(turn.answer ?? "").map((part, index) =>
          part.type === "text" ? (
            <Typeset key={index} text={part.text} />
          ) : (
            <sup key={index} className={styles.marker}>
              <a
                href={`#${anchor(part.number)}`}
                aria-label={t("toCitation", { number: part.number })}
              >
                {part.number}
              </a>
            </sup>
          ),
        )}
      </p>
      <ol className={styles.citations} aria-label={t("citations")}>
        {turn.citations.map((citation) => (
          <li key={citation.number} id={anchor(citation.number)} className={styles.citation}>
            <span className={styles.citationNumber} aria-hidden>
              {citation.number}
            </span>
            <div className={styles.citationBody}>
              <p className={styles.citationRef}>{citation.citation}</p>
              <blockquote className={styles.quote}>
                <Typeset text={`«${citation.quote}»`} />
              </blockquote>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
