import type { CSSProperties } from "react";

import styles from "./progress.module.css";

/** Determinate when `value` (0–1) is given, indeterminate otherwise. */
export function ProgressBar({ value, label }: { value?: number; label: string }) {
  const percent =
    value === undefined ? undefined : Math.round(Math.min(Math.max(value, 0), 1) * 100);
  return (
    <div
      className={styles.track}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
    >
      <span
        className={`${styles.bar} ${percent === undefined ? styles.indeterminate : ""}`}
        style={{ "--progress": `${percent ?? 35}%` } as CSSProperties}
      />
    </div>
  );
}
