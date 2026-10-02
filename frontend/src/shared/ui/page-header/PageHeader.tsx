import type { ReactNode } from "react";

import styles from "./page-header.module.css";
import { Typeset } from "@/shared/typography/Typeset";

export function PageHeader({
  title,
  meta,
  leading,
  actions,
}: {
  title: string;
  meta?: ReactNode;
  /** Above the title: a back link or a breadcrumb. */
  leading?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <div className={styles.titles}>
        {leading ? <div className={styles.leading}>{leading}</div> : null}
        <h1 className={styles.title}>
          <Typeset text={title} />
        </h1>
        {meta ? <div className={styles.meta}>{meta}</div> : null}
      </div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}
