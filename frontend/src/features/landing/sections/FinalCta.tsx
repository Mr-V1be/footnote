import { IconArrowRight } from "@tabler/icons-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Button } from "@/shared/ui/button/Button";

import band from "./band.module.css";
import styles from "./final-cta.module.css";

/** The last band: the same one action as the first screen. */
export async function FinalCta({ demo }: { demo: boolean }) {
  const t = await getTranslations("landing.final");
  return (
    <section className={`${band.band} ${band.surface}`} aria-labelledby="final-title">
      <div className={`${band.inner} ${styles.final}`}>
        <h2 id="final-title" className={band.title}>
          {t("title")}
        </h2>
        <p className={band.lead}>{t("lead")}</p>
        <div className={styles.actions}>
          <Button asChild variant="primary" icon={<IconArrowRight stroke={1.75} />}>
            <Link href={demo ? "/demo" : "/auth/login"}>{t("tryDemo")}</Link>
          </Button>
          <Button asChild variant="secondary">
            <a href="/auth/login">{t("signIn")}</a>
          </Button>
        </div>
      </div>
    </section>
  );
}
