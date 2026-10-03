import { IconLock } from "@tabler/icons-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Brand } from "@/features/shell/Brand";
import { Button } from "@/shared/ui/button/Button";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./access-screen.module.css";

/** Full-page refusal: the user is signed in but may not see this organization. */
export async function AccessScreen({
  reason,
}: {
  reason: "noOrganizations" | "notMember" | "notOperator";
}) {
  const t = await getTranslations("access");
  return (
    <div className={styles.screen}>
      <header className={styles.brand}>
        <Brand />
      </header>
      <StatePanel
        icon={<IconLock stroke={1.75} />}
        title={t(`${reason}Title`)}
        description={t(`${reason}Description`)}
        role="alert"
        action={
          <div className={styles.actions}>
            {reason !== "noOrganizations" ? (
              <Button asChild variant="primary">
                <Link href="/">{t("toMyOrganizations")}</Link>
              </Button>
            ) : null}
            <form action="/auth/logout" method="post">
              <Button type="submit" variant="secondary">
                {t("signOut")}
              </Button>
            </form>
          </div>
        }
      />
    </div>
  );
}
