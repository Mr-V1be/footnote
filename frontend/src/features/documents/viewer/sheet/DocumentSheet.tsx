"use client";

import { IconScan } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { Fragment, useMemo, type Ref } from "react";

import type { DocumentStructure } from "@/shared/api/types";

import { BlockView } from "./BlockView";
import { marksByBlock, NO_MARKS, type Footnote, type Highlight } from "../footnotes";
import styles from "./sheet.module.css";

const RECOGNISED = new Set(["pdf_ocr", "pdf_mixed"]);

/**
 * The document itself, on a sheet of paper, with footnote markers in the
 * text and, for a while, the places of an open document-wide finding.
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
  const byBlock = useMemo(() => marksByBlock(footnotes, highlights), [footnotes, highlights]);
  const recognised = RECOGNISED.has(structure.version.method ?? "");
  return (
    <article ref={sheetRef} className={styles.sheet} lang="ru">
      {recognised ? (
        <p className={styles.notice}>
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
