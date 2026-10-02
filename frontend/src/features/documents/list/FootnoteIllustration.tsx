import styles from "./illustration.module.css";

/** The product in one picture: a line of a document, its marker and the margin note. */
export function FootnoteIllustration() {
  return (
    <svg className={styles.illustration} viewBox="0 0 240 132" role="presentation" aria-hidden>
      <rect className={styles.sheet} x="8" y="8" width="140" height="116" rx="6" />
      <rect className={styles.line} x="24" y="26" width="92" height="6" rx="3" />
      <rect className={styles.line} x="24" y="42" width="108" height="6" rx="3" />
      <rect className={styles.mark} x="24" y="56" width="60" height="10" rx="3" />
      <rect className={styles.line} x="26" y="58" width="56" height="6" rx="3" />
      <text className={styles.marker} x="88" y="60">
        1
      </text>
      <rect className={styles.line} x="98" y="58" width="34" height="6" rx="3" />
      <rect className={styles.line} x="24" y="74" width="100" height="6" rx="3" />
      <rect className={styles.line} x="24" y="90" width="80" height="6" rx="3" />
      <path className={styles.link} d="M96 61 C 128 61, 140 52, 164 52" />
      <rect className={styles.note} x="164" y="34" width="68" height="40" rx="6" />
      <text className={styles.marker} x="172" y="50">
        1
      </text>
      <rect className={styles.noteLine} x="182" y="45" width="40" height="5" rx="2.5" />
      <rect className={styles.noteLine} x="182" y="57" width="30" height="5" rx="2.5" />
    </svg>
  );
}
