"use client";

import { useCallback, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

import { anchors } from "@/features/documents/viewer/footnotes";
import type { CheckDefinition } from "@/shared/api/types";

import type { NumberedFinding } from "../findings";
import { FindingCard } from "./FindingCard";
import { locateOf, type CardHandlers } from "./FindingList";
import styles from "./result.module.css";

/** Room between two notes in the margin, in pixels of layout. */
const GAP_PX = 12;

interface Placement {
  tops: ReadonlyMap<string, number>;
  height: number;
}

/**
 * Margin notes level with their markers, like footnotes set in the margin of
 * a printed page. Notes never overlap: one that would is pushed down, and the
 * selected note is set exactly at its marker, moving its neighbours aside.
 */
export function SidenoteColumn({
  items,
  checks,
  handlers,
  sheet,
}: {
  items: readonly NumberedFinding[];
  checks: ReadonlyMap<string, CheckDefinition>;
  handlers: CardHandlers;
  /** The document sheet; its size changes move the markers. */
  sheet: HTMLElement | null;
}) {
  const zone = useRef<HTMLOListElement>(null);
  const cards = useRef(new Map<string, HTMLElement>());
  const [placement, setPlacement] = useState<Placement>({ tops: new Map(), height: 0 });
  const selectedId = handlers.selectedId;

  const layout = useCallback(() => {
    const element = zone.current;
    if (!element) return;
    const origin = element.getBoundingClientRect().top;
    const entries = items.map((item) => {
      const mark = item.footnote
        ? document.getElementById(anchors.mark(item.footnote.number))
        : null;
      return {
        id: item.finding.id,
        desired: mark ? mark.getBoundingClientRect().top - origin : 0,
        height: cards.current.get(item.finding.id)?.offsetHeight ?? 0,
      };
    });
    const tops = new Map<string, number>();
    let cursor = 0;
    for (const entry of entries) {
      const top = Math.max(entry.desired, cursor);
      tops.set(entry.id, top);
      cursor = top + entry.height + GAP_PX;
    }
    const selected = entries.findIndex((entry) => entry.id === selectedId);
    if (selected >= 0) {
      // Pull the selected note up to its marker; the notes above give way.
      const target = entries[selected];
      if (target) {
        let ceiling = Math.max(0, target.desired);
        tops.set(target.id, Math.min(tops.get(target.id) ?? ceiling, ceiling));
        for (let index = selected - 1; index >= 0; index -= 1) {
          const entry = entries[index];
          if (!entry) continue;
          const top = Math.min(tops.get(entry.id) ?? 0, ceiling - GAP_PX - entry.height);
          tops.set(entry.id, Math.max(top, 0));
          ceiling = tops.get(entry.id) ?? 0;
        }
        cursor = (tops.get(target.id) ?? 0) + target.height + GAP_PX;
        for (const entry of entries.slice(selected + 1)) {
          const top = Math.max(entry.desired, cursor);
          tops.set(entry.id, top);
          cursor = top + entry.height + GAP_PX;
        }
      }
    }
    setPlacement({ tops, height: Math.max(cursor - GAP_PX, 0) });
  }, [items, selectedId]);

  useLayoutEffect(() => {
    layout();
    const observer = new ResizeObserver(() => layout());
    if (zone.current) observer.observe(zone.current);
    if (sheet) observer.observe(sheet);
    for (const card of cards.current.values()) observer.observe(card);
    window.addEventListener("resize", layout);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", layout);
    };
  }, [layout, sheet]);

  return (
    <ol
      ref={zone}
      className={styles.sidenotes}
      style={{ "--sidenotes-height": `${placement.height}px` } as CSSProperties}
    >
      {items.map((item) => {
        const top = placement.tops.get(item.finding.id);
        return (
          <li
            key={item.finding.id}
            className={styles.sidenote}
            data-placed={top !== undefined || undefined}
            style={{ "--sidenote-top": `${top ?? 0}px` } as CSSProperties}
            onMouseEnter={() => handlers.onHover(item.footnote?.number ?? null)}
            onMouseLeave={() => handlers.onHover(null)}
          >
            <FindingCard
              cardRef={(element) => {
                if (element) cards.current.set(item.finding.id, element);
                else cards.current.delete(item.finding.id);
              }}
              item={item}
              check={checks.get(item.finding.checkCode)}
              expanded={selectedId === item.finding.id}
              active={
                selectedId === item.finding.id ||
                (item.footnote !== null && handlers.activeNumber === item.footnote.number)
              }
              busy={handlers.busyId === item.finding.id}
              onSelect={() => handlers.onSelect(item.finding.id)}
              onReview={(review) => handlers.onReview(item, review)}
              onLocate={locateOf(item, handlers)}
            />
          </li>
        );
      })}
    </ol>
  );
}
