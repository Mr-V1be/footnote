"use client";

import { IconArrowUp } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState, type KeyboardEvent } from "react";

import { TextArea } from "@/shared/ui/field/Field";
import { IconButton } from "@/shared/ui/icon-button/IconButton";

import styles from "./ask.module.css";

const QUESTION_MAX_LENGTH = 2000;

/** Where a question is written: Enter sends it, Shift+Enter starts a new line. */
export function Composer({ busy, onAsk }: { busy: boolean; onAsk: (question: string) => void }) {
  const t = useTranslations("ask");
  const [question, setQuestion] = useState("");
  const send = () => {
    const text = question.trim();
    if (!text || busy) return;
    onAsk(text);
    setQuestion("");
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  };
  return (
    <form
      className={styles.composer}
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <TextArea
        className={styles.composerInput}
        value={question}
        rows={2}
        maxLength={QUESTION_MAX_LENGTH}
        placeholder={t("placeholder")}
        aria-label={t("question")}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <IconButton
        type="submit"
        variant="primary"
        label={t("send")}
        icon={<IconArrowUp stroke={2} />}
        disabled={busy || !question.trim()}
      />
    </form>
  );
}
