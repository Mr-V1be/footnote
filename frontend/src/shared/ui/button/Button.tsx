import { Slot } from "radix-ui";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { Spinner } from "../spinner/Spinner";
import styles from "./button.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading icon; replaced by a spinner while loading. */
  icon?: ReactNode;
  loading?: boolean;
  block?: boolean;
  /** Render the child element (e.g. a link) with button styling. */
  asChild?: boolean;
}

export function buttonClassName({
  variant = "secondary",
  size = "md",
  block = false,
  className,
}: Pick<ButtonProps, "variant" | "size" | "block" | "className">): string {
  return [styles.button, styles[variant], styles[size], block ? styles.block : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
}

export function Button({
  variant,
  size,
  icon,
  loading = false,
  block,
  asChild = false,
  className,
  children,
  disabled,
  type,
  ...rest
}: ButtonProps) {
  const Component = asChild ? Slot.Root : "button";
  const leading = loading ? <Spinner /> : icon ? <span className={styles.icon}>{icon}</span> : null;
  return (
    <Component
      className={buttonClassName({ variant, size, block, className })}
      disabled={asChild ? undefined : disabled || loading}
      aria-busy={loading || undefined}
      type={asChild ? undefined : (type ?? "button")}
      {...rest}
    >
      {leading}
      {asChild ? <Slot.Slottable>{children}</Slot.Slottable> : children}
    </Component>
  );
}
