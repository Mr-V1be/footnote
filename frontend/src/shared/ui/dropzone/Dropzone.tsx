"use client";

import { IconFileUpload } from "@tabler/icons-react";
import { useId, useRef, useState, type DragEvent } from "react";

import styles from "./dropzone.module.css";

/** Pick or drop a file. Texts come from the caller; the component knows no domain. */
export function Dropzone({
  accept,
  title,
  hint,
  onFile,
  disabled = false,
}: {
  accept: string;
  title: string;
  hint: string;
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function drop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file && !disabled) onFile(file);
  }

  return (
    <label
      htmlFor={id}
      className={`${styles.zone} ${dragging ? styles.dragging : ""} ${disabled ? styles.disabled : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={drop}
    >
      <IconFileUpload className={styles.icon} stroke={1.5} aria-hidden />
      <span className={styles.title}>{title}</span>
      <span className={styles.hint}>{hint}</span>
      <input
        ref={input}
        id={id}
        className={styles.input}
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />
    </label>
  );
}
