import type { ReactNode } from "react";

import styles from "./page.module.css";

/**
 * The column of a page's content within the frame: its measure, the gutters
 * and room at the bottom for a floating action and the home indicator.
 */
export function Page({
  children,
  width = "content",
  spacing = "md",
  busy = false,
}: {
  children: ReactNode;
  /** `narrow` for settings and forms, `content` for lists and dashboards. */
  width?: "content" | "narrow";
  spacing?: "md" | "lg";
  /** The content is a placeholder of what is loading. */
  busy?: boolean;
}) {
  return (
    <div
      className={`${styles.page} ${styles[width]} ${styles[spacing]}`}
      aria-busy={busy || undefined}
    >
      {children}
    </div>
  );
}
