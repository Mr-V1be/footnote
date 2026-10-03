"use client";

import type { ReactNode } from "react";

import { Button } from "../button/Button";
import { Dialog, DialogClose, DialogContent } from "../dialog/Dialog";
import styles from "./confirm-dialog.module.css";

/**
 * Confirmation of a dangerous action that names its consequences
 * ("5 documents will be deleted"), not "Are you sure?".
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  consequences,
  confirmLabel,
  cancelLabel,
  closeLabel,
  pending = false,
  error,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  consequences: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  closeLabel: string;
  pending?: boolean;
  /** Why the last attempt failed, shown above the actions. */
  error?: string | null;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={title}
        closeLabel={closeLabel}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="secondary">{cancelLabel}</Button>
            </DialogClose>
            <Button variant="danger" loading={pending} onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </>
        }
      >
        <div className={styles.consequences}>{consequences}</div>
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
