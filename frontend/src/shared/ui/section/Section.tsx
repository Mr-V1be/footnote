import { useId, type ReactNode } from "react";

import styles from "./section.module.css";

/** A titled part of a page, with its own actions on the right of the title. */
export function Section({
  title,
  meta,
  actions,
  children,
}: {
  title: string;
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section className={styles.section} aria-labelledby={id}>
      <header className={styles.header}>
        <div className={styles.titles}>
          <h2 id={id} className={styles.title}>
            {title}
          </h2>
          {meta ? <div className={styles.meta}>{meta}</div> : null}
        </div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </header>
      {children}
    </section>
  );
}
