import type { CSSProperties, ReactNode } from "react";

import styles from "./meter.module.css";

/** From this share of a limit a meter warns. */
const WARN_SHARE = 0.8;

/**
 * How much of a limit is used. `value` alone, without a limit, is a count
 * with no bar. The text (e.g. "12 из 50") is formatted by the caller.
 */
export function Meter({
  label,
  value,
  max,
  text,
}: {
  label: string;
  value: number;
  max: number | null;
  text: ReactNode;
}) {
  const share = max && max > 0 ? Math.min(value / max, 1) : null;
  const tone =
    share === null
      ? "normal"
      : value >= (max ?? 0)
        ? "full"
        : share >= WARN_SHARE
          ? "warn"
          : "normal";
  return (
    <div className={styles.meter}>
      <div className={styles.line}>
        <span className={styles.label}>{label}</span>
        <span className={`${styles.text} ${styles[tone]}`}>{text}</span>
      </div>
      {share !== null ? (
        <div
          className={styles.track}
          role="meter"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={max ?? 0}
          aria-valuenow={value}
        >
          <span
            className={`${styles.bar} ${styles[tone]}`}
            style={{ "--share": `${Math.round(share * 100)}%` } as CSSProperties}
          />
        </div>
      ) : null}
    </div>
  );
}
