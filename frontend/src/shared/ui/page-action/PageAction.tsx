import type { ReactNode } from "react";

import { Button } from "../button/Button";
import styles from "./page-action.module.css";

/**
 * The one main action of a page: in the header on wide screens, a floating
 * button in the thumb zone on phones and tablets. Put it in the header.
 */
export function PageAction({
  icon,
  label,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <div className={styles.action}>
      <Button variant="primary" icon={icon} onClick={onClick}>
        {label}
      </Button>
    </div>
  );
}
