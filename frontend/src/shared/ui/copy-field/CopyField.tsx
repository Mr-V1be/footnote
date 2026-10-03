"use client";

import { IconCheck, IconCopy } from "@tabler/icons-react";
import { useEffect, useId, useState } from "react";

import { Button } from "../button/Button";
import styles from "./copy-field.module.css";

const COPIED_FOR_MS = 2000;

/** A value to take elsewhere (a token, a secret, a link) with a copy button. */
export function CopyField({
  label,
  value,
  copyLabel,
  copiedLabel,
}: {
  label: string;
  value: string;
  copyLabel: string;
  copiedLabel: string;
}) {
  const id = useId();
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_FOR_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
  };
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <div className={styles.row}>
        <input
          id={id}
          className={styles.value}
          value={value}
          readOnly
          spellCheck={false}
          onFocus={(event) => event.currentTarget.select()}
        />
        <Button
          variant="secondary"
          icon={copied ? <IconCheck stroke={1.75} /> : <IconCopy stroke={1.75} />}
          onClick={() => void copy()}
          aria-live="polite"
        >
          {copied ? copiedLabel : copyLabel}
        </Button>
      </div>
    </div>
  );
}
