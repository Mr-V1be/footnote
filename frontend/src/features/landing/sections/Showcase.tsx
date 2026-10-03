import { IconQuote } from "@tabler/icons-react";
import { getTranslations } from "next-intl/server";

import { DeviceFrame } from "@/shared/ui/device-frame/DeviceFrame";

import { LoopVideo } from "../media/LoopVideo";
import band from "./band.module.css";
import styles from "./showcase.module.css";

/** The moments the product is about, each next to its recording: the wide
    screen gets a row of its own, the two phone screens share the next one. */
const WIDE = { id: "footnotes", video: "footnotes", device: "laptop" } as const;
const PAIR = [
  { id: "autofix", video: "autofix", device: "phone" },
  { id: "ask", video: "ask", device: "phone" },
] as const;

type Moment = typeof WIDE | (typeof PAIR)[number];

async function MomentCard({ moment }: { moment: Moment }) {
  const t = await getTranslations("landing.showcase");
  return (
    <article
      className={`${styles.moment} ${styles[moment.device]}`}
      aria-labelledby={`moment-${moment.id}`}
    >
      <div className={styles.media}>
        <DeviceFrame kind={moment.device} label={t(`${moment.id}.label`)}>
          <LoopVideo
            name={moment.video}
            label={t(`${moment.id}.label`)}
            width={moment.device === "laptop" ? 1280 : 390}
            height={moment.device === "laptop" ? 800 : 844}
          />
        </DeviceFrame>
      </div>
      <div className={styles.copy}>
        <h3 id={`moment-${moment.id}`} className={styles.title}>
          {t(`${moment.id}.title`)}
        </h3>
        <p className={styles.text}>{t(`${moment.id}.text`)}</p>
        <p className={styles.point}>
          <IconQuote stroke={1.75} aria-hidden />
          {t(`${moment.id}.point`)}
        </p>
      </div>
    </article>
  );
}

export async function Showcase() {
  const t = await getTranslations("landing.showcase");
  return (
    <section id="features" className={band.band} aria-labelledby="showcase-title">
      <div className={band.inner}>
        <header className={band.heading}>
          <p className={band.eyebrow}>{t("eyebrow")}</p>
          <h2 id="showcase-title" className={band.title}>
            {t("title")}
          </h2>
        </header>
        <div className={styles.moments}>
          <MomentCard moment={WIDE} />
          <div className={styles.pair}>
            {PAIR.map((moment) => (
              <MomentCard key={moment.id} moment={moment} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
