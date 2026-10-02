import type { ReactNode } from "react";

import styles from "./badge.module.css";

export type BadgeTone = "neutral" | "ink" | "success" | "advice" | "important" | "critical";

export function Badge({
  tone = "neutral",
  dot = false,
  pulse = false,
  children,
}: {
  tone?: BadgeTone;
  /** A leading status dot; `pulse` animates it for work in progress. */
  dot?: boolean;
  pulse?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      {dot ? <span className={`${styles.dot} ${pulse ? styles.pulse : ""}`} aria-hidden /> : null}
      {children}
    </span>
  );
}
