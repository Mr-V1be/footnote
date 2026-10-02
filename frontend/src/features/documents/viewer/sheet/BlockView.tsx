"use client";

import type { CSSProperties } from "react";

import type { Block } from "@/shared/api/types";

import { anchors, type Footnote } from "../footnotes";
import { InlineText } from "./InlineText";
import styles from "./sheet.module.css";
import { TableView } from "./TableView";

const HEADING_TAGS = ["h2", "h3", "h4"] as const;
/** Recognised text below this confidence is underlined as uncertain. */
const LOW_CONFIDENCE = 0.8;

/** Indents beyond these bounds come from measurement noise, not from the author. */
const MIN_FIRST_LINE_INDENT_MM = -20;
const MAX_LEFT_INDENT_MM = 120;

/**
 * Source indents are mirrored so the reader sees the document as written.
 * They only apply to left-aligned and justified text: in centred lines the
 * measured offset is the centring itself.
 */
function indentStyle(block: Block): CSSProperties {
  const paragraph = block.paragraph;
  const indented = paragraph?.alignment !== "center" && paragraph?.alignment !== "right";
  const first = indented
    ? Math.max(paragraph?.firstLineIndentMm ?? 0, MIN_FIRST_LINE_INDENT_MM)
    : 0;
  const left = indented
    ? Math.min(Math.max(paragraph?.leftIndentMm ?? 0, 0), MAX_LEFT_INDENT_MM)
    : 0;
  return {
    "--indent-first": `${first}mm`,
    "--indent-left": `${left}mm`,
    "--list-level": block.kind === "list_item" ? (block.level ?? 0) : 0,
  } as CSSProperties;
}

/**
 * The source alignment is kept as data: the sheet decides how to set it on
 * screen (justified text falls back to ragged right on a short measure).
 */
function alignment(block: Block): string | undefined {
  return block.paragraph?.alignment ?? undefined;
}

export function BlockView({ block, footnotes }: { block: Block; footnotes: readonly Footnote[] }) {
  const id = anchors.block(block.ordinal);
  const lowConfidence = block.confidence !== null && block.confidence < LOW_CONFIDENCE;
  switch (block.kind) {
    case "heading": {
      const Tag =
        HEADING_TAGS[Math.min(Math.max((block.level ?? 1) - 1, 0), HEADING_TAGS.length - 1)] ??
        "h2";
      return (
        <Tag
          id={id}
          className={styles.heading}
          style={indentStyle(block)}
          data-align={alignment(block)}
          data-level={block.level ?? 1}
        >
          {block.label ? <span className={styles.headingLabel}>{block.label}</span> : null}
          <InlineText text={block.text} footnotes={footnotes} />
        </Tag>
      );
    }
    case "list_item":
      return (
        <div id={id} className={styles.listItem} style={indentStyle(block)}>
          <span className={styles.listLabel}>{block.label}</span>
          <div className={styles.measure} data-align={alignment(block)}>
            <p className={`${styles.listText} ${lowConfidence ? styles.uncertain : ""}`}>
              <InlineText text={block.text} footnotes={footnotes} />
            </p>
          </div>
        </div>
      );
    case "table":
      return <TableView id={id} block={block} footnotes={footnotes} />;
    case "paragraph":
      return (
        <div
          id={id}
          className={`${styles.paragraph} ${styles.measure}`}
          style={indentStyle(block)}
          data-align={alignment(block)}
        >
          <p className={lowConfidence ? styles.uncertain : undefined}>
            <InlineText text={block.text} footnotes={footnotes} />
          </p>
        </div>
      );
  }
}
