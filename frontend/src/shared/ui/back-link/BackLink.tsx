import { IconArrowLeft } from "@tabler/icons-react";
import Link from "next/link";

import styles from "./back-link.module.css";

/** Up one level, above a page title: to the list the page belongs to. */
export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className={styles.back}>
      <IconArrowLeft stroke={1.75} aria-hidden />
      {label}
    </Link>
  );
}
