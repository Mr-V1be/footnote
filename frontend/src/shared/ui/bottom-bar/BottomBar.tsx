import { VisuallyHidden } from "radix-ui";
import type { ReactNode } from "react";

import styles from "./bottom-bar.module.css";

export interface BottomBarItem {
  id: string;
  icon: ReactNode;
  /** One or two short words: it sits under the icon at 360 px. */
  label: string;
  /** A count on the icon, e.g. the number of findings. */
  badge?: number;
  /** What the badge means, for screen readers ("5 замечаний"). */
  badgeLabel?: string;
  /** Whether the panel this item opens is open. */
  expanded?: boolean;
  onClick: () => void;
}

/**
 * Actions of a screen in the thumb zone of a phone or tablet: equal buttons,
 * an icon over a short label, clear of the home indicator. Hidden where the
 * screen has room for its panels (the consumer decides with `className`).
 */
export function BottomBar({
  label,
  items,
  className,
}: {
  label: string;
  items: readonly BottomBarItem[];
  className?: string;
}) {
  return (
    <nav className={`${styles.bar} ${className ?? ""}`} aria-label={label}>
      <ul className={styles.items}>
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={styles.item}
              aria-expanded={item.expanded}
              onClick={item.onClick}
            >
              <span className={styles.icon} aria-hidden>
                {item.icon}
                {item.badge !== undefined ? (
                  <span className={styles.badge}>{item.badge}</span>
                ) : null}
              </span>
              <span className={styles.label}>{item.label}</span>
              {item.badgeLabel ? (
                <VisuallyHidden.Root>, {item.badgeLabel}</VisuallyHidden.Root>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
