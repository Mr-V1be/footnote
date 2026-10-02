import type { CSSProperties } from "react";

import styles from "./skeleton.module.css";

/** Placeholder in the shape of the content that is loading. */
export function Skeleton({
  width = "100%",
  height,
  shape = "line",
}: {
  width?: string;
  height?: string;
  shape?: "line" | "block" | "circle";
}) {
  const style = { "--skeleton-width": width, "--skeleton-height": height } as CSSProperties;
  return <span className={`${styles.skeleton} ${styles[shape]}`} style={style} aria-hidden />;
}
