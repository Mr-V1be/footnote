import styles from "./spinner.module.css";

/** Inline progress for an action in flight (inside buttons). Content loading uses skeletons. */
export function Spinner({ label }: { label?: string }) {
  return (
    <span
      className={styles.spinner}
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={!label}
    />
  );
}
