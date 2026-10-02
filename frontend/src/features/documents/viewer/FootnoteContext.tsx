"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { anchors } from "./footnotes";

const FLASH_CLASS = "isFlashing";
const FLASH_MS = 1200;

interface FootnoteState {
  /** The footnote under the pointer or keyboard focus, highlighted in text and margin. */
  active: number | null;
  setActive: (number: number | null) => void;
  /** Bring the marked text into view. */
  revealMark: (number: number) => void;
  /** Bring a block of the document into view. */
  revealBlock: (ordinal: number) => void;
  /** Bring the margin card into view (opens the panel where it is hidden). */
  revealCard: (number: number) => void;
}

/**
 * Where a revealed card is shown: in the margin beside its marker, which the
 * reader is already looking at, or in a panel opened over the document.
 */
export type CardPlace = "margin" | "panel";

const FootnoteContext = createContext<FootnoteState | null>(null);

function scrollAndFlash(id: string, block: ScrollLogicalPosition = "center") {
  const element = document.getElementById(id);
  if (!element) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  element.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block });
  element.classList.add(FLASH_CLASS);
  window.setTimeout(() => element.classList.remove(FLASH_CLASS), FLASH_MS);
}

export function FootnoteProvider({
  onRevealCard,
  children,
}: {
  /** Called before scrolling to a card: select it, open the panel on a phone. */
  onRevealCard: (number: number) => CardPlace;
  children: ReactNode;
}) {
  const [active, setActive] = useState<number | null>(null);
  const revealMark = useCallback((number: number) => scrollAndFlash(anchors.mark(number)), []);
  const revealBlock = useCallback((ordinal: number) => scrollAndFlash(anchors.block(ordinal)), []);
  const revealCard = useCallback(
    (number: number) => {
      const place = onRevealCard(number);
      // In the margin the card stands level with the marker: scroll only as
      // much as it takes to show it whole, so the text does not jump away.
      const block = place === "margin" ? "nearest" : "center";
      // Two frames: the panel opens and the card takes its place before scrolling.
      window.requestAnimationFrame(() =>
        window.requestAnimationFrame(() => scrollAndFlash(anchors.footnote(number), block)),
      );
    },
    [onRevealCard],
  );
  const value = useMemo(
    () => ({ active, setActive, revealMark, revealBlock, revealCard }),
    [active, revealMark, revealBlock, revealCard],
  );
  return <FootnoteContext value={value}>{children}</FootnoteContext>;
}

export function useFootnotes(): FootnoteState {
  const state = useContext(FootnoteContext);
  if (!state) throw new Error("useFootnotes must be used inside FootnoteProvider");
  return state;
}
