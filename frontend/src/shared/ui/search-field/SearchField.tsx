"use client";

import { IconSearch, IconX } from "@tabler/icons-react";
import { useRef } from "react";

import styles from "./search-field.module.css";

export function SearchField({
  value,
  onChange,
  label,
  placeholder,
  clearLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  clearLabel: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={styles.field}>
      <IconSearch className={styles.icon} stroke={1.75} aria-hidden />
      <input
        ref={input}
        className={styles.input}
        type="search"
        value={value}
        aria-label={label}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        enterKeyHint="search"
        autoComplete="off"
      />
      {value ? (
        <button
          type="button"
          className={styles.clear}
          aria-label={clearLabel}
          onClick={() => {
            onChange("");
            input.current?.focus();
          }}
        >
          <IconX stroke={1.75} />
        </button>
      ) : null}
    </div>
  );
}
