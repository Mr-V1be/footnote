import type { ReactNode } from "react";

import styles from "./state-panel.module.css";

export type StateTone = "neutral" | "critical" | "ink";

/**
 * Empty, error and no-access states: what happened and the one thing to do
 * next. `illustration` replaces the icon tile when a state deserves a picture.
 */
export function StatePanel({
  icon,
  illustration,
  title,
  description,
  action,
  tone = "neutral",
  role,
}: {
  icon?: ReactNode;
  illustration?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: StateTone;
  role?: "alert" | "status";
}) {
  return (
    <section className={styles.panel} role={role}>
      {illustration ?? (
        <span className={`${styles.icon} ${styles[tone]}`} aria-hidden>
          {icon}
        </span>
      )}
      <h2 className={styles.title}>{title}</h2>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </section>
  );
}
