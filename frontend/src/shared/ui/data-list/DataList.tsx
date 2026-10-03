import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import styles from "./data-list.module.css";

/**
 * A list of records on one surface: people, keys, invoices, events. Each row
 * has a title with a line of facts under it; values for comparison (`aside`)
 * sit in a column on wide screens and under the facts on phones; row actions
 * stay at the end of the row.
 */
export function DataList({
  label,
  children,
  busy = false,
  reserveActions = false,
}: {
  label: string;
  children: ReactNode;
  busy?: boolean;
  /** Keep the actions column in rows without actions, so values line up. */
  reserveActions?: boolean;
}) {
  const classes = [styles.list, busy ? styles.busy : "", reserveActions ? styles.reserve : ""];
  return (
    <ul className={classes.join(" ")} aria-label={label} aria-busy={busy}>
      {children}
    </ul>
  );
}

export function DataRow({
  leading,
  title,
  description,
  aside,
  actions,
  tone = "default",
}: {
  /** An avatar or an icon before the title. */
  leading?: ReactNode;
  title: ReactNode;
  /** Facts under the title: short spans, separated by the layout. */
  description?: ReactNode;
  /** Values to compare between rows: a status, an amount, a date. */
  aside?: ReactNode;
  /** One or two controls, usually a menu. */
  actions?: ReactNode;
  /** A muted row is still listed but no longer in effect (revoked, removed). */
  tone?: "default" | "muted";
}) {
  return (
    <li
      className={`${styles.row} ${tone === "muted" ? styles.muted : ""}`}
      data-leading={leading ? "" : undefined}
    >
      {leading ? <span className={styles.leading}>{leading}</span> : null}
      <div className={styles.main}>
        <div className={styles.title}>{title}</div>
        {description ? <div className={styles.description}>{description}</div> : null}
      </div>
      {aside ? <div className={styles.aside}>{aside}</div> : null}
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </li>
  );
}

/** A row title that opens the record: the whole row is its click target. */
export function DataRowLink(props: ComponentProps<typeof Link>) {
  return <Link {...props} className={`${styles.link} ${props.className ?? ""}`} />;
}

export function DataListSkeleton({ rows = 4, label }: { rows?: number; label: string }) {
  return (
    <ul className={styles.list} aria-label={label} aria-busy>
      {Array.from({ length: rows }, (_, index) => (
        <li key={index} className={`${styles.row} ${styles.skeletonRow}`} data-leading="">
          <span className={`${styles.leading} ${styles.skeletonCircle}`} />
          <span className={styles.main}>
            <span className={styles.skeletonLine} />
            <span className={`${styles.skeletonLine} ${styles.skeletonShort}`} />
          </span>
        </li>
      ))}
    </ul>
  );
}
