import styles from "./skip-link.module.css";

/** The first stop of the keyboard: straight to the page's content. */
export function SkipLink({ target, label }: { target: string; label: string }) {
  return (
    <a className={styles.skip} href={`#${target}`}>
      {label}
    </a>
  );
}
