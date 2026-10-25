import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { Brand } from "@/features/shell/Brand";
import { Button } from "@/shared/ui/button/Button";
import { SkipLink } from "@/shared/ui/skip-link/SkipLink";

import styles from "./landing.module.css";
import { LanguageMenu } from "./LanguageMenu";
import { ThemeMenu } from "./ThemeMenu";

/** Sections of the public site: anchors on the landing and the methodology page. */
const NAV = [
  { href: "/#how", label: "how" },
  { href: "/#features", label: "features" },
  { href: "/#pricing", label: "pricing" },
  { href: "/how-we-check", label: "methodology" },
] as const;

/** The frame of the public pages: the wordmark, sections, sign-in and the demo. */
export async function MarketingShell({ demo, children }: { demo: boolean; children: ReactNode }) {
  const t = await getTranslations("landing");
  return (
    <div className={styles.site}>
      <SkipLink target="main" label={t("skip")} />
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.home} aria-label={t("home")}>
            <Brand />
          </Link>
          <nav className={styles.nav} aria-label={t("navLabel")}>
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className={styles.navLink}>
                {t(`nav.${item.label}`)}
              </Link>
            ))}
          </nav>
          <div className={styles.headerActions}>
            <LanguageMenu />
            <ThemeMenu />
            <Button asChild variant="ghost">
              <a href="/auth/login">{t("signIn")}</a>
            </Button>
            <Button asChild variant="primary">
              <Link href={demo ? "/demo" : "/auth/login"}>
                <span className={styles.long}>{t("tryDemo")}</span>
                <span className={styles.short}>{t("tryDemoShort")}</span>
              </Link>
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className={styles.main} tabIndex={-1}>
        {children}
      </main>
      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div>
            <Brand />
            <p className={styles.footerNote}>{t("footerNote")}</p>
          </div>
          <nav className={styles.footerLinks} aria-label={t("footerLabel")}>
            <Link href="/how-we-check">{t("nav.methodology")}</Link>
            <Link href="/#pricing">{t("nav.pricing")}</Link>
            {demo ? <Link href="/demo">{t("tryDemo")}</Link> : null}
            <a href="/auth/login">{t("signIn")}</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
