"use client";

import { useTranslations } from "next-intl";

import type { DocumentListItem } from "@/shared/api/types";

import styles from "./document-list.module.css";
import { DocumentRow } from "./DocumentRow";

export function DocumentList({
  items,
  organization,
}: {
  items: DocumentListItem[];
  organization: string;
}) {
  const t = useTranslations("documents.columns");
  return (
    <div className={styles.list}>
      <div className={styles.head} aria-hidden>
        <span>{t("title")}</span>
        <span>{t("kind")}</span>
        <span>{t("version")}</span>
        <span>{t("updated")}</span>
        <span>{t("status")}</span>
      </div>
      <ul className={styles.rows}>
        {items.map((item) => (
          <DocumentRow key={item.id} item={item} organization={organization} />
        ))}
      </ul>
    </div>
  );
}

export function DocumentListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className={styles.list} aria-busy>
      <ul className={styles.rows}>
        {Array.from({ length: rows }, (_, index) => (
          <li key={index} className={`${styles.row} ${styles.skeletonRow}`}>
            <span className={styles.skeletonIcon} />
            <span className={styles.skeletonLines}>
              <span className={styles.skeletonLine} />
              <span className={`${styles.skeletonLine} ${styles.skeletonShort}`} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
