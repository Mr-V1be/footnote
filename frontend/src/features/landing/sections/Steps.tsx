import { IconFileUpload, IconListCheck, IconWand, type Icon } from "@tabler/icons-react";
import { getTranslations } from "next-intl/server";

import { ThemedImage } from "../media/ThemedImage";
import band from "./band.module.css";
import styles from "./steps.module.css";

/** The three steps of the product, each with the screen it happens on. */
const STEPS: readonly { id: "upload" | "check" | "fix"; icon: Icon; image: string }[] = [
  { id: "upload", icon: IconFileUpload, image: "step-upload" },
  { id: "check", icon: IconListCheck, image: "step-check" },
  { id: "fix", icon: IconWand, image: "step-fix" },
];

export async function Steps() {
  const t = await getTranslations("landing.steps");
  return (
    <section id="how" className={`${band.band} ${band.surface}`} aria-labelledby="steps-title">
      <div className={band.inner}>
        <header className={band.heading}>
          <p className={band.eyebrow}>{t("eyebrow")}</p>
          <h2 id="steps-title" className={band.title}>
            {t("title")}
          </h2>
        </header>
        <ol className={styles.steps}>
          {STEPS.map((step, index) => {
            const Glyph = step.icon;
            return (
              <li key={step.id} className={styles.step}>
                <div className={styles.shot}>
                  <ThemedImage
                    name={step.image}
                    alt={t(`${step.id}.alt`)}
                    width={1200}
                    height={800}
                  />
                </div>
                <div className={styles.text}>
                  <span className={styles.number} aria-hidden>
                    {index + 1}
                  </span>
                  <div>
                    <h3 className={styles.stepTitle}>
                      <Glyph stroke={1.75} aria-hidden />
                      {t(`${step.id}.title`)}
                    </h3>
                    <p className={styles.stepText}>{t(`${step.id}.text`)}</p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
