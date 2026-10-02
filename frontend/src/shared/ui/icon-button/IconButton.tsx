"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

import { buttonClassName, type ButtonSize, type ButtonVariant } from "../button/Button";
import { Tooltip } from "../tooltip/Tooltip";
import styles from "./icon-button.module.css";

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Accessible name, also shown as a tooltip. */
  label: string;
  icon: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  tooltip?: boolean;
}

export function IconButton({
  label,
  icon,
  variant = "ghost",
  size = "md",
  tooltip = true,
  className,
  type,
  ...rest
}: IconButtonProps) {
  const button = (
    <button
      type={type ?? "button"}
      aria-label={label}
      className={`${buttonClassName({ variant, size })} ${styles.square} ${styles[size]} ${className ?? ""}`}
      {...rest}
    >
      {icon}
    </button>
  );
  return tooltip ? <Tooltip content={label}>{button}</Tooltip> : button;
}
