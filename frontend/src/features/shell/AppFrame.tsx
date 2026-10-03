"use client";

import { IconMenu2 } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { Drawer, DrawerContent, DrawerTrigger } from "@/shared/ui/drawer/Drawer";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { SkipLink } from "@/shared/ui/skip-link/SkipLink";

import styles from "./app-frame.module.css";
import { Brand } from "./Brand";
import { DemoMark } from "./DemoMark";
import { UserMenu } from "./UserMenu";

/**
 * The frame of every signed-in page: a sidebar on wide screens, a top bar
 * with the same sidebar in a drawer on narrow ones.
 */
export function AppFrame({
  sidebar,
  children,
}: {
  sidebar: (onNavigate?: () => void) => ReactNode;
  children: ReactNode;
}) {
  const t = useTranslations();
  const [drawerOpen, setDrawerOpen] = useState(false);
  return (
    <>
      <SkipLink target="main" label={t("nav.skipToContent")} />
      <div className={styles.shell}>
        <aside className={styles.sidebar} aria-label={t("nav.label")}>
          {sidebar()}
        </aside>
        <header className={styles.topbar}>
          <Drawer open={drawerOpen} onOpenChange={setDrawerOpen}>
            <DrawerTrigger asChild>
              <IconButton
                label={t("nav.openMenu")}
                icon={<IconMenu2 stroke={1.75} />}
                tooltip={false}
              />
            </DrawerTrigger>
            <DrawerContent side="left" title={t("nav.menu")} closeLabel={t("common.close")}>
              {sidebar(() => setDrawerOpen(false))}
            </DrawerContent>
          </Drawer>
          <Brand />
          <DemoMark />
          <span className={styles.spacer} />
          <UserMenu compact />
        </header>
        <main id="main" className={styles.main} tabIndex={-1}>
          {children}
        </main>
      </div>
    </>
  );
}
