"use client";

import { IconCheck } from "@tabler/icons-react";
import { DropdownMenu as Primitive } from "radix-ui";
import type { ReactNode } from "react";

import styles from "./menu.module.css";

export const Menu = Primitive.Root;
export const MenuTrigger = Primitive.Trigger;
export const MenuGroup = Primitive.Group;
export const MenuRadioGroup = Primitive.RadioGroup;

export function MenuContent({
  align = "start",
  side = "bottom",
  children,
}: {
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
  children: ReactNode;
}) {
  return (
    <Primitive.Portal>
      <Primitive.Content
        className={styles.content}
        align={align}
        side={side}
        sideOffset={6}
        collisionPadding={8}
      >
        {children}
      </Primitive.Content>
    </Primitive.Portal>
  );
}

export function MenuItem({
  icon,
  onSelect,
  children,
  asChild,
  tone = "default",
}: {
  icon?: ReactNode;
  onSelect?: () => void;
  children: ReactNode;
  asChild?: boolean;
  tone?: "default" | "critical";
}) {
  return (
    <Primitive.Item
      className={`${styles.item} ${tone === "critical" ? styles.critical : ""}`}
      onSelect={onSelect}
      asChild={asChild}
    >
      {asChild ? (
        children
      ) : (
        <>
          {icon ? <span className={styles.icon}>{icon}</span> : null}
          <span className={styles.text}>{children}</span>
        </>
      )}
    </Primitive.Item>
  );
}

export function MenuRadioItem({ value, children }: { value: string; children: ReactNode }) {
  return (
    <Primitive.RadioItem className={styles.item} value={value}>
      <span className={styles.icon}>
        <Primitive.ItemIndicator>
          <IconCheck stroke={1.75} />
        </Primitive.ItemIndicator>
      </span>
      <span className={styles.text}>{children}</span>
    </Primitive.RadioItem>
  );
}

export function MenuCheckboxItem({
  checked,
  onCheckedChange,
  children,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  children: ReactNode;
}) {
  return (
    <Primitive.CheckboxItem
      className={styles.item}
      checked={checked}
      onCheckedChange={(value) => onCheckedChange(value === true)}
      // Several options are usually toggled in a row: keep the menu open.
      onSelect={(event) => event.preventDefault()}
    >
      <span className={styles.icon}>
        <Primitive.ItemIndicator>
          <IconCheck stroke={1.75} />
        </Primitive.ItemIndicator>
      </span>
      <span className={styles.text}>{children}</span>
    </Primitive.CheckboxItem>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <Primitive.Label className={styles.label}>{children}</Primitive.Label>;
}

export function MenuSeparator() {
  return <Primitive.Separator className={styles.separator} />;
}
