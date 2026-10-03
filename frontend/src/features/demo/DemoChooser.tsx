import {
  IconAlertTriangle,
  IconArrowRight,
  IconCrown,
  IconEye,
  IconScale,
  IconServer2,
  type Icon,
} from "@tabler/icons-react";
import { getTranslations } from "next-intl/server";

import type { DemoAccount, DemoRole } from "@/server/demo/accounts";
import { Avatar } from "@/shared/ui/avatar/Avatar";
import { Button } from "@/shared/ui/button/Button";
import { Notice } from "@/shared/ui/notice/Notice";

import styles from "./demo.module.css";

const ICONS: Record<DemoRole, Icon> = {
  owner: IconCrown,
  lawyer: IconScale,
  observer: IconEye,
  operator: IconServer2,
};

/**
 * The roles of the demo stand side by side: who the account is, what the
 * role may do, and one button that signs in as it.
 */
export async function DemoChooser({
  accounts,
  failed,
}: {
  accounts: readonly DemoAccount[];
  failed: boolean;
}) {
  const t = await getTranslations("demo");
  return (
    <section className={styles.screen} aria-labelledby="demo-title">
      <header className={styles.heading}>
        <h1 id="demo-title" className={styles.title}>
          {t("title")}
        </h1>
        <p className={styles.lead}>{t("lead")}</p>
      </header>
      {failed ? (
        <Notice icon={<IconAlertTriangle stroke={1.75} />} tone="critical" role="alert">
          {t("failed")}
        </Notice>
      ) : null}
      <ul className={styles.roles}>
        {accounts.map((account) => {
          const Glyph = ICONS[account.role];
          return (
            <li key={account.role} className={styles.role}>
              <div className={styles.roleHead}>
                <span className={styles.icon} aria-hidden>
                  <Glyph stroke={1.75} />
                </span>
                <h2 className={styles.roleTitle}>{t(`roles.${account.role}.title`)}</h2>
              </div>
              <p className={styles.roleText}>{t(`roles.${account.role}.text`)}</p>
              <div className={styles.person}>
                <Avatar name={account.name} />
                <span className={styles.personText}>
                  <span className={styles.name}>{account.name}</span>
                  <span className={styles.organization}>
                    {account.organization ?? t("platform")}
                  </span>
                </span>
              </div>
              <form action="/auth/demo" method="post">
                <input type="hidden" name="role" value={account.role} />
                <Button
                  type="submit"
                  variant="primary"
                  block
                  icon={<IconArrowRight stroke={1.75} />}
                >
                  {t("enter")}
                </Button>
              </form>
            </li>
          );
        })}
      </ul>
      <p className={styles.note}>{t("note")}</p>
    </section>
  );
}
