"use client";

import { useTranslations } from "next-intl";

import type { Block } from "@/shared/api/types";

import type { BlockMarks, Footnote, Highlight } from "../footnotes";
import { InlineText } from "./InlineText";
import styles from "./sheet.module.css";

const CELL_SEPARATOR_LENGTH = 1;

/**
 * Offsets refer to the table text (cells joined by tabs, rows by line
 * breaks); they are re-based onto the cell they fall into.
 */
function inCells<T extends { start: number; end: number }>(
  block: Block,
  spans: readonly T[],
): Map<string, T[]> {
  const byCell = new Map<string, T[]>();
  let offset = 0;
  block.table?.forEach((row, rowIndex) => {
    row.forEach((cell, cellIndex) => {
      const length = cell.text.length;
      for (const span of spans) {
        // A span is marked in the cell it starts in, up to the end of that cell.
        const { start, end } = span;
        if (start >= offset && start < offset + length) {
          const key = `${rowIndex}:${cellIndex}`;
          const local = {
            ...span,
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

export function TableView({ id, block, marks }: { id: string; block: Block; marks: BlockMarks }) {
  const t = useTranslations("viewer");
  const footnotes = inCells<Footnote>(block, marks.footnotes);
  const highlights = inCells<Highlight>(block, marks.highlights);
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
                    marks={{
                      footnotes: footnotes.get(`${rowIndex}:${cellIndex}`) ?? [],
                      highlights: highlights.get(`${rowIndex}:${cellIndex}`) ?? [],
                    }}
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
