import { IconArrowRight, IconLogin2 } from "@tabler/icons-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Button } from "@/shared/ui/button/Button";
import { DeviceFrame } from "@/shared/ui/device-frame/DeviceFrame";

import { LoopVideo } from "../media/LoopVideo";
import styles from "./hero.module.css";

/** The first screen: what the product is, one action, and the product itself. */
export async function Hero({ demo, checks }: { demo: boolean; checks: number | null }) {
  const t = await getTranslations("landing.hero");
  return (
    <section className={styles.hero} aria-labelledby="hero-title">
      <div className={styles.inner}>
        <div className={styles.copy}>
          <p className={styles.eyebrow}>{t("eyebrow")}</p>
          <h1 id="hero-title" className={styles.title}>
            {t("title")}
            <sup className={styles.mark} aria-hidden>
              1
            </sup>
          </h1>
          <p className={styles.lead}>{t("lead")}</p>
          <div className={styles.actions}>
            <Button asChild variant="primary" icon={<IconArrowRight stroke={1.75} />}>
              <Link href={demo ? "/demo" : "/auth/login"}>{t("tryDemo")}</Link>
            </Button>
            <Button asChild variant="secondary" icon={<IconLogin2 stroke={1.75} />}>
              <a href="/auth/login">{t("signIn")}</a>
            </Button>
          </div>
          {checks ? <p className={styles.note}>{t("note", { count: checks })}</p> : null}
          <p className={styles.footnote}>
            <sup aria-hidden>1</sup> {t("footnote")}
          </p>
        </div>
        <div className={styles.visual}>
          <div className={styles.laptop}>
            <DeviceFrame kind="laptop" label={t("laptopLabel")}>
              <LoopVideo name="result" label={t("laptopLabel")} width={1280} height={800} />
            </DeviceFrame>
          </div>
          <div className={styles.phone}>
            <DeviceFrame kind="phone" label={t("phoneLabel")}>
              <LoopVideo name="result-phone" label={t("phoneLabel")} width={390} height={844} />
            </DeviceFrame>
          </div>
        </div>
      </div>
    </section>
  );
}
