"use client";

import { ToggleGroup } from "radix-ui";
import type { ReactNode } from "react";

import styles from "./segmented.module.css";

export interface Segment<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

/** Two or three short, mutually exclusive modes. */
export function SegmentedControl<T extends string>({
  value,
  onChange,
  segments,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  segments: readonly Segment<T>[];
  label: string;
}) {
  return (
    <ToggleGroup.Root
      type="single"
      className={styles.group}
      value={value}
      aria-label={label}
      onValueChange={(next) => {
        const match = segments.find((segment) => segment.value === next);
        if (match) onChange(match.value);
      }}
    >
      {segments.map((segment) => (
        <ToggleGroup.Item key={segment.value} value={segment.value} className={styles.item}>
          {segment.icon ? <span className={styles.icon}>{segment.icon}</span> : null}
          <span>{segment.label}</span>
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
