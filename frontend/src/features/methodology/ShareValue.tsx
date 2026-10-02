"use client";

import { Tooltip } from "@/shared/ui/tooltip/Tooltip";

import styles from "./methodology.module.css";
import type { ShareText } from "./useQualityFormat";

/** A precision or recall figure; when it has no number, the reason is a hover away. */
export function ShareValue({ text, size = "md" }: { text: ShareText; size?: "md" | "lg" }) {
  const value = (
    <span className={styles.share} data-size={size} data-empty={text.hint !== null || undefined}>
      {text.value}
    </span>
  );
  if (text.hint === null) return value;
  return (
    <Tooltip content={text.hint}>
      <span tabIndex={0} className={styles.hinted} aria-label={`${text.value}. ${text.hint}`}>
        {value}
      </span>
    </Tooltip>
  );
}
