import { typeset, typesetRuns, type TypesetText } from "./typeset";
import styles from "./typography.module.css";

/** Renders prepared text, or a slice of it, with its unbreakable runs. */
export function TypesetRuns({
  value,
  start,
  end,
}: {
  value: TypesetText;
  start?: number;
  end?: number;
}) {
  return typesetRuns(value, start, end).map((run, index) =>
    run.keep ? (
      <span key={index} className={styles.keep}>
        {run.text}
      </span>
    ) : (
      run.text
    ),
  );
}

/** Interface text from data (titles, values, references) set by the typographic rules. */
export function Typeset({ text }: { text: string }) {
  return <TypesetRuns value={typeset(text)} />;
}
