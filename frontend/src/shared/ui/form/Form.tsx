import type { FormEvent, ReactNode } from "react";

import styles from "./form.module.css";

/**
 * Fields of a task, one under the other. A submit button outside the form
 * (in a dialog's footer) refers to it by `id`.
 */
export function Form({
  id,
  onSubmit,
  children,
}: {
  id?: string;
  onSubmit?: () => void;
  children: ReactNode;
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit?.();
  };
  return onSubmit ? (
    <form id={id} className={styles.form} onSubmit={submit} noValidate>
      {children}
    </form>
  ) : (
    <div className={styles.form}>{children}</div>
  );
}

/** Why the task did not go through, above its actions. */
export function FormError({ children }: { children: ReactNode }) {
  return (
    <p className={styles.error} role="alert">
      {children}
    </p>
  );
}

/** Two short fields side by side where there is room. */
export function FormRow({ children }: { children: ReactNode }) {
  return <div className={styles.row}>{children}</div>;
}
