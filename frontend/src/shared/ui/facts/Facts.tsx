import type { ReactNode } from "react";

import styles from "./facts.module.css";

export interface Fact {
  term: string;
  value: ReactNode;
}

/** Name–value pairs: details of a file, a plan, a system. */
export function Facts({ items, columns = 1 }: { items: readonly Fact[]; columns?: 1 | 2 }) {
  return (
    <dl className={`${styles.facts} ${columns === 2 ? styles.two : ""}`}>
      {items.map((item) => (
        <div key={item.term} className={styles.fact}>
          <dt>{item.term}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
