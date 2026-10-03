import type { ReactNode } from "react";

import styles from "./device-frame.module.css";

/**
 * A screen of the product shown in the shape of the device it runs on: a
 * laptop for the wide layout, a phone for the narrow one. Drawn with tokens,
 * no images; the content (a picture or a video) fills the screen.
 */
export function DeviceFrame({
  kind,
  label,
  children,
}: {
  kind: "laptop" | "phone";
  /** What the screen shows, for screen readers. */
  label: string;
  children: ReactNode;
}) {
  return (
    <figure className={`${styles.frame} ${styles[kind]}`} aria-label={label}>
      <div className={styles.screen}>{children}</div>
      {kind === "laptop" ? <div className={styles.base} aria-hidden /> : null}
    </figure>
  );
}
