"use client";

import { useTranslations } from "next-intl";

import type { Block } from "@/shared/api/types";

import type { Footnote } from "../footnotes";
import { InlineText } from "./InlineText";
import styles from "./sheet.module.css";

const CELL_SEPARATOR_LENGTH = 1;

/**
 * Offsets refer to the table text (cells joined by tabs, rows by line
 * breaks); they are re-based onto the cell they fall into.
 */
function cellFootnotes(block: Block, footnotes: readonly Footnote[]): Map<string, Footnote[]> {
  const byCell = new Map<string, Footnote[]>();
  let offset = 0;
  block.table?.forEach((row, rowIndex) => {
    row.forEach((cell, cellIndex) => {
      const length = cell.text.length;
      for (const footnote of footnotes) {
        // A span is marked in the cell it starts in, up to the end of that cell.
        const { start, end } = footnote;
        if (start >= offset && start < offset + length) {
          const key = `${rowIndex}:${cellIndex}`;
          const local = {
            ...footnote,
            start: start - offset,
            end: Math.min(end, offset + length) - offset,
          };
          byCell.set(key, [...(byCell.get(key) ?? []), local]);
        }
      }
      offset += length + CELL_SEPARATOR_LENGTH;
    });
  });
  return byCell;
}

export function TableView({
  id,
  block,
  footnotes,
}: {
  id: string;
  block: Block;
  footnotes: readonly Footnote[];
}) {
  const t = useTranslations("viewer");
  const placed = cellFootnotes(block, footnotes);
  return (
    <div id={id} className={styles.tableWrap} role="region" aria-label={t("table")} tabIndex={0}>
      <table className={styles.table}>
        <tbody>
          {block.table?.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} colSpan={cell.colSpan} rowSpan={cell.rowSpan}>
                  <InlineText
                    text={cell.text.replaceAll("\n", " ")}
                    footnotes={placed.get(`${rowIndex}:${cellIndex}`) ?? []}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
