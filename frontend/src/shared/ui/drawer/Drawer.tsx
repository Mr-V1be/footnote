"use client";

import { IconX } from "@tabler/icons-react";
import { Dialog as Primitive } from "radix-ui";
import type { ReactNode } from "react";

import styles from "./drawer.module.css";

export const Drawer = Primitive.Root;
export const DrawerTrigger = Primitive.Trigger;
export const DrawerClose = Primitive.Close;

export type DrawerSide = "left" | "right" | "bottom";

/** A panel that slides over the page: navigation, outlines, side information. */
export function DrawerContent({
  side,
  title,
  closeLabel,
  children,
}: {
  side: DrawerSide;
  title: string;
  closeLabel: string;
  children: ReactNode;
}) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className={styles.overlay} />
      <Primitive.Content
        className={`${styles.content} ${styles[side]}`}
        aria-describedby={undefined}
      >
        <header className={styles.header}>
          {side === "bottom" ? <span className={styles.grabber} aria-hidden /> : null}
          <Primitive.Title className={styles.title}>{title}</Primitive.Title>
          <Primitive.Close className={styles.close} aria-label={closeLabel}>
            <IconX stroke={1.75} />
          </Primitive.Close>
        </header>
        <div className={styles.body}>{children}</div>
      </Primitive.Content>
    </Primitive.Portal>
  );
}
