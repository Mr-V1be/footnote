import type { ReactNode } from "react";

import styles from "./notice.module.css";

export type NoticeTone = "neutral" | "ink" | "warning" | "critical" | "success";

/** A line of status inside a page: what holds now and, if any, what to do. */
export function Notice({
  icon,
  tone = "neutral",
  title,
  children,
  action,
  role,
}: {
  icon: ReactNode;
  tone?: NoticeTone;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  role?: "status" | "alert";
}) {
  return (
    <div className={`${styles.notice} ${styles[tone]}`} role={role}>
      <span className={styles.icon} aria-hidden>
        {icon}
      </span>
      <div className={styles.text}>
        {title ? <p className={styles.title}>{title}</p> : null}
        {children ? <div className={styles.body}>{children}</div> : null}
      </div>
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}
