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
  /** Bring the margin card into view (opens the panel where it is hidden). */
  revealCard: (number: number) => void;
}

const FootnoteContext = createContext<FootnoteState | null>(null);

function scrollAndFlash(id: string) {
  const element = document.getElementById(id);
  if (!element) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  element.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
  element.classList.add(FLASH_CLASS);
  window.setTimeout(() => element.classList.remove(FLASH_CLASS), FLASH_MS);
}

export function FootnoteProvider({
  onRevealCard,
  children,
}: {
  /** Called before scrolling to a card: select it, open the panel on a phone. */
  onRevealCard: (number: number) => void;
  children: ReactNode;
}) {
  const [active, setActive] = useState<number | null>(null);
  const revealMark = useCallback((number: number) => scrollAndFlash(anchors.mark(number)), []);
  const revealCard = useCallback(
    (number: number) => {
      onRevealCard(number);
      // Two frames: the panel opens and the card takes its place before scrolling.
      window.requestAnimationFrame(() =>
        window.requestAnimationFrame(() => scrollAndFlash(anchors.footnote(number))),
      );
    },
    [onRevealCard],
  );
  const value = useMemo(
    () => ({ active, setActive, revealMark, revealCard }),
    [active, revealMark, revealCard],
  );
  return <FootnoteContext value={value}>{children}</FootnoteContext>;
}

export function useFootnotes(): FootnoteState {
  const state = useContext(FootnoteContext);
  if (!state) throw new Error("useFootnotes must be used inside FootnoteProvider");
  return state;
}
