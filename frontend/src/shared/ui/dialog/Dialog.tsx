"use client";

import { IconX } from "@tabler/icons-react";
import { Dialog as Primitive } from "radix-ui";
import type { ReactNode } from "react";

import styles from "./dialog.module.css";

export const Dialog = Primitive.Root;
export const DialogTrigger = Primitive.Trigger;
export const DialogClose = Primitive.Close;

/**
 * A modal task. Centred on wide screens, a bottom sheet on phones so the
 * actions stay within reach of the thumb.
 */
export function DialogContent({
  title,
  description,
  closeLabel,
  footer,
  children,
}: {
  title: string;
  description?: string;
  closeLabel: string;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className={styles.overlay} />
      <Primitive.Content
        className={styles.content}
        // Without a description the dialog is labelled by its title only.
        {...(description ? {} : { "aria-describedby": undefined })}
      >
        <header className={styles.header}>
          <div className={styles.heading}>
            <Primitive.Title className={styles.title}>{title}</Primitive.Title>
            {description ? (
              <Primitive.Description className={styles.description}>
                {description}
              </Primitive.Description>
            ) : null}
          </div>
          <Primitive.Close className={styles.close} aria-label={closeLabel}>
            <IconX stroke={1.75} />
          </Primitive.Close>
        </header>
        <div className={styles.body}>{children}</div>
        {footer ? <footer className={styles.footer}>{footer}</footer> : null}
      </Primitive.Content>
    </Primitive.Portal>
  );
}
