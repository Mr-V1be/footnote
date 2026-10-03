"use client";

import { IconCheck } from "@tabler/icons-react";
import { Checkbox } from "radix-ui";
import { useId } from "react";

import styles from "./checkbox-group.module.css";

export interface CheckboxOption {
  value: string;
  label: string;
  hint?: string;
}

/** Several of many: a list of checkboxes under one legend. */
export function CheckboxGroup({
  legend,
  options,
  value,
  onChange,
  error,
}: {
  legend: string;
  options: readonly CheckboxOption[];
  value: readonly string[];
  onChange: (value: string[]) => void;
  error?: string;
}) {
  const id = useId();
  const errorId = `${id}-error`;
  const toggle = (option: string, checked: boolean) =>
    onChange(
      checked
        ? options
            .map((item) => item.value)
            .filter((item) => item === option || value.includes(item))
        : value.filter((item) => item !== option),
    );
  return (
    <fieldset
      className={styles.group}
      aria-describedby={error ? errorId : undefined}
      aria-invalid={error ? true : undefined}
    >
      <legend className={styles.legend}>{legend}</legend>
      <ul className={styles.options}>
        {options.map((option) => {
          const optionId = `${id}-${option.value}`;
          return (
            <li key={option.value} className={styles.option}>
              <Checkbox.Root
                id={optionId}
                className={styles.box}
                checked={value.includes(option.value)}
                onCheckedChange={(checked) => toggle(option.value, checked === true)}
              >
                <Checkbox.Indicator className={styles.indicator}>
                  <IconCheck stroke={2.25} />
                </Checkbox.Indicator>
              </Checkbox.Root>
              <label htmlFor={optionId} className={styles.text}>
                <span className={styles.label}>{option.label}</span>
                {option.hint ? <span className={styles.hint}>{option.hint}</span> : null}
              </label>
            </li>
          );
        })}
      </ul>
      {error ? (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
