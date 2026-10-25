"use client";

import { IconLanguage, IconScan } from "@tabler/icons-react";
import { useLocale, useTranslations } from "next-intl";
import { Fragment, useMemo, type Ref } from "react";

import type { DocumentStructure } from "@/shared/api/types";
import { DOCUMENT_LOCALE } from "@/shared/i18n/locales";

import { BlockView } from "./BlockView";
import { marksByBlock, NO_MARKS, type Footnote, type Highlight } from "../footnotes";
import styles from "./sheet.module.css";

const RECOGNISED = new Set(["pdf_ocr", "pdf_mixed"]);

/**
 * The document itself, on a sheet of paper, with footnote markers in the
 * text and, for a while, the places of an open document-wide finding. Its
 * text is the original's; a reader of another language is told so.
 */
export function DocumentSheet({
  structure,
  footnotes,
  highlights = [],
  sheetRef,
}: {
  structure: DocumentStructure;
  footnotes: readonly Footnote[];
  highlights?: readonly Highlight[];
  sheetRef?: Ref<HTMLElement>;
}) {
  const t = useTranslations("viewer");
  const locale = useLocale();
  const byBlock = useMemo(() => marksByBlock(footnotes, highlights), [footnotes, highlights]);
  const recognised = RECOGNISED.has(structure.version.method ?? "");
  return (
    <article ref={sheetRef} className={styles.sheet} lang={DOCUMENT_LOCALE}>
      {locale !== DOCUMENT_LOCALE ? (
        <p className={styles.caption} lang={locale}>
          <IconLanguage stroke={1.75} aria-hidden />
          {t("originalLanguage")}
        </p>
      ) : null}
      {recognised ? (
        <p className={styles.notice} lang={locale}>
          <IconScan stroke={1.75} aria-hidden />
          {t("lowConfidence")}
        </p>
      ) : null}
      {structure.blocks.map((block, index) => {
        const previousPage = structure.blocks[index - 1]?.page;
        const pageBreak =
          block.page !== null &&
          previousPage !== undefined &&
          previousPage !== null &&
          block.page !== previousPage;
        return (
          <Fragment key={block.ordinal}>
            {pageBreak ? (
              <div className={styles.pageBreak} aria-hidden>
                <span>{t("page", { number: block.page ?? 0 })}</span>
              </div>
            ) : null}
            <BlockView block={block} marks={byBlock.get(block.ordinal) ?? NO_MARKS} />
          </Fragment>
        );
      })}
    </article>
  );
}
