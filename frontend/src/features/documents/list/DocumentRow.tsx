"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import type { DocumentListItem } from "@/shared/api/types";
import { CheckStatus } from "@/features/checks/CheckStatus";
import { useFormatDate } from "@/shared/format/useFormatDate";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";

import { FileTypeIcon } from "../FileTypeIcon";
import styles from "./document-list.module.css";
import { Typeset } from "@/shared/typography/Typeset";

export function DocumentRow({
  item,
  organization,
}: {
  item: DocumentListItem;
  organization: string;
}) {
  const t = useTranslations("documents");
  const kindLabel = useCodeLabel("kinds");
  const formatDate = useFormatDate();
  return (
    <li className={styles.row}>
      <div className={styles.titleCell}>
        <FileTypeIcon format={item.format} className={styles.fileIcon} />
        <div className={styles.titleText}>
          <Link href={`/o/${organization}/documents/${item.id}`} className={styles.title}>
            <Typeset text={item.title} />
          </Link>
          <span className={styles.secondary}>
            {item.createdByName ? (
              <span>{t("uploadedBy", { name: item.createdByName })}</span>
            ) : null}
            {item.pageCount ? <span>{t("pages", { count: item.pageCount })}</span> : null}
          </span>
        </div>
      </div>
      {/* Separate columns on wide screens, one line of facts on narrow ones. */}
      <div className={styles.facts}>
        <span className={styles.kind}>{kindLabel(item.kind)}</span>
        <span className={styles.version}>
          <span className={styles.versionWord}>{t("versionWord")} </span>
          {item.latestVersion}
        </span>
        <time className={styles.updated} dateTime={item.updatedAt}>
          {formatDate(item.updatedAt)}
        </time>
      </div>
      <span className={styles.status}>
        <CheckStatus item={item} />
      </span>
    </li>
  );
}
