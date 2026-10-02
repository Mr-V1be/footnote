import { IconCompass } from "@tabler/icons-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Button } from "@/shared/ui/button/Button";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./standalone.module.css";

export default async function NotFound() {
  const t = await getTranslations("errors");
  return (
    <div className={styles.screen}>
      <StatePanel
        icon={<IconCompass stroke={1.75} />}
        title={t("notFoundTitle")}
        description={t("notFoundDescription")}
        action={
          <Button asChild variant="primary">
            <Link href="/">{t("home")}</Link>
          </Button>
        }
      />
    </div>
  );
}
