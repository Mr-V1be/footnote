import type { ReactNode } from "react";

import styles from "./state-panel.module.css";

/** `bare` drops the icon tile, for illustrations that bring their own shape. */
export type StateTone = "neutral" | "critical" | "ink" | "bare";

/** Empty, error and no-access states: what happened and the one thing to do next. */
export function StatePanel({
  icon,
  title,
  description,
  action,
  tone = "neutral",
  role,
}: {
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: StateTone;
  role?: "alert" | "status";
}) {
  return (
    <section className={styles.panel} role={role}>
      <span className={`${styles.icon} ${styles[tone]}`} aria-hidden>
        {icon}
      </span>
      <h2 className={styles.title}>{title}</h2>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </section>
  );
}
