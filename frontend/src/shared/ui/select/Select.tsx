"use client";

import { IconCheck, IconChevronDown } from "@tabler/icons-react";
import { Select as Primitive } from "radix-ui";
import type { ReactNode } from "react";

import styles from "./select.module.css";

export interface SelectOption {
  value: string;
  label: string;
}

/** Choosing one value out of many. */
export function Select({
  value,
  onValueChange,
  options,
  label,
  icon,
  id,
  block = false,
  size = "md",
}: {
  value: string;
  onValueChange: (value: string) => void;
  options: readonly SelectOption[];
  /** Accessible name when no visible label is attached. */
  label?: string;
  icon?: ReactNode;
  id?: string;
  block?: boolean;
  size?: "sm" | "md";
}) {
  return (
    <Primitive.Root value={value} onValueChange={onValueChange}>
      <Primitive.Trigger
        id={id}
        className={`${styles.trigger} ${block ? styles.block : ""} ${size === "sm" ? styles.sm : ""}`}
        aria-label={label}
      >
        {icon ? <span className={styles.icon}>{icon}</span> : null}
        <span className={styles.value}>
          <Primitive.Value />
        </span>
        <Primitive.Icon className={styles.chevron}>
          <IconChevronDown stroke={1.75} />
        </Primitive.Icon>
      </Primitive.Trigger>
      <Primitive.Portal>
        <Primitive.Content
          className={styles.content}
          position="popper"
          sideOffset={6}
          collisionPadding={8}
        >
          <Primitive.Viewport className={styles.viewport}>
            {options.map((option) => (
              <Primitive.Item key={option.value} value={option.value} className={styles.item}>
                <Primitive.ItemText>{option.label}</Primitive.ItemText>
                <Primitive.ItemIndicator className={styles.check}>
                  <IconCheck stroke={1.75} />
                </Primitive.ItemIndicator>
              </Primitive.Item>
            ))}
          </Primitive.Viewport>
        </Primitive.Content>
      </Primitive.Portal>
    </Primitive.Root>
  );
}
