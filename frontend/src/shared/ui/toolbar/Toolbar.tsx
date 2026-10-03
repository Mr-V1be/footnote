import type { ReactNode } from "react";

import styles from "./toolbar.module.css";

/** Filters and view controls above a list, wrapping on narrow screens. */
export function Toolbar({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.toolbar} role="group" aria-label={label}>
      {children}
    </div>
  );
}
