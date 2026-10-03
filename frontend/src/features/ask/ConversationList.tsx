"use client";

import { IconMessages } from "@tabler/icons-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import type { ConversationSummary } from "@/shared/api/types";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";

import styles from "./ask.module.css";

/** Earlier conversations of the person, the latest first. */
export function ConversationList({
  organization,
  conversations,
  currentId,
  onNavigate,
}: {
  organization: string;
  conversations: readonly ConversationSummary[] | undefined;
  currentId: string | null;
  onNavigate?: () => void;
}) {
  const t = useTranslations("ask");
  const formatDate = useFormatDate();
  if (!conversations) {
    return (
      <div className={styles.historySkeleton} aria-busy>
        <Skeleton width="80%" />
        <Skeleton width="65%" />
        <Skeleton width="72%" />
      </div>
    );
  }
  if (conversations.length === 0) {
    return (
      <p className={styles.historyEmpty}>
        <IconMessages stroke={1.75} aria-hidden />
        {t("noHistory")}
      </p>
    );
  }
  return (
    <ul className={styles.history}>
      {conversations.map((item) => (
        <li key={item.id}>
          <Link
            href={`/o/${organization}/ask/${item.id}`}
            className={`${styles.historyLink} ${item.id === currentId ? styles.historyActive : ""}`}
            aria-current={item.id === currentId ? "page" : undefined}
            onClick={onNavigate}
          >
            <span className={styles.historyTitle}>{item.title}</span>
            <time className={styles.historyDate} dateTime={item.updatedAt}>
              {formatDate(item.updatedAt)}
            </time>
          </Link>
        </li>
      ))}
    </ul>
  );
}
