"use client";

import { IconScan } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { Fragment, useMemo, type Ref } from "react";

import type { DocumentStructure } from "@/shared/api/types";

import { BlockView } from "./BlockView";
import { footnotesByBlock, type Footnote } from "./footnotes";
import styles from "./sheet.module.css";

const RECOGNISED = new Set(["pdf_ocr", "pdf_mixed"]);

/** The document itself, on a sheet of paper, with footnote markers in the text. */
export function DocumentSheet({
  structure,
  footnotes,
  sheetRef,
}: {
  structure: DocumentStructure;
  footnotes: readonly Footnote[];
  sheetRef?: Ref<HTMLElement>;
}) {
  const t = useTranslations("viewer");
  const byBlock = useMemo(() => footnotesByBlock(footnotes), [footnotes]);
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
            <BlockView block={block} footnotes={byBlock.get(block.ordinal) ?? []} />
          </Fragment>
        );
      })}
    </article>
  );
}
