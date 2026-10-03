"use client";

import { Switch as Primitive } from "radix-ui";
import { useId } from "react";

import styles from "./switch.module.css";

/** An on/off setting with its label (and an optional hint) beside it. */
export function Switch({
  label,
  hint,
  checked,
  onCheckedChange,
  disabled = false,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.text}>
        <span className={styles.label}>{label}</span>
        {hint ? (
          <span id={hintId} className={styles.hint}>
            {hint}
          </span>
        ) : null}
      </label>
      <Primitive.Root
        id={id}
        className={styles.track}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-describedby={hint ? hintId : undefined}
      >
        <Primitive.Thumb className={styles.thumb} />
      </Primitive.Root>
    </div>
  );
}
