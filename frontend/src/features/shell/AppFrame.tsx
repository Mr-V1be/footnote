"use client";

import { IconMenu2 } from "@tabler/icons-react";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { MembershipProvider, type MembershipState } from "@/features/session/membership";
import { Drawer, DrawerContent, DrawerTrigger } from "@/shared/ui/drawer/Drawer";
import { IconButton } from "@/shared/ui/icon-button/IconButton";

import styles from "./app-shell.module.css";
import { Brand } from "./Brand";
import { DemoMark } from "./DemoMark";
import { SidebarContent } from "./SidebarContent";
import { UserMenu } from "./UserMenu";

export function AppShell({ state, children }: { state: MembershipState; children: ReactNode }) {
  const t = useTranslations();
  const [drawerOpen, setDrawerOpen] = useState(false);
  return (
    <MembershipProvider value={state}>
      <a className={styles.skip} href="#main">
        {t("nav.skipToContent")}
      </a>
      <div className={styles.shell}>
        <aside className={styles.sidebar} aria-label={t("nav.label")}>
          <SidebarContent />
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
              <SidebarContent onNavigate={() => setDrawerOpen(false)} />
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
    </MembershipProvider>
  );
}
