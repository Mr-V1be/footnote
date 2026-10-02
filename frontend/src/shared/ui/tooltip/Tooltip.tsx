"use client";

import { Tooltip as Primitive } from "radix-ui";
import type { ReactElement, ReactNode } from "react";

import styles from "./tooltip.module.css";

const OPEN_DELAY_MS = 400;

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <Primitive.Provider delayDuration={OPEN_DELAY_MS}>{children}</Primitive.Provider>;
}

export function Tooltip({
  content,
  side = "top",
  children,
}: {
  content: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  children: ReactElement;
}) {
  return (
    <Primitive.Root>
      <Primitive.Trigger asChild>{children}</Primitive.Trigger>
      <Primitive.Portal>
        <Primitive.Content
          className={styles.content}
          side={side}
          sideOffset={6}
          collisionPadding={8}
        >
          {content}
        </Primitive.Content>
      </Primitive.Portal>
    </Primitive.Root>
  );
}
