import { IconAlertTriangle, IconCreditCard, IconFlask } from "@tabler/icons-react";
import { getFormatter, getTranslations } from "next-intl/server";

import { Brand } from "@/features/shell/Brand";
import type { TestPayment } from "@/shared/api/types";
import { Button } from "@/shared/ui/button/Button";
import { Notice } from "@/shared/ui/notice/Notice";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./checkout.module.css";

const KOPECKS_IN_RUBLE = 100;

/**
 * The page of the test payment provider: an amount, what it is for and two
 * outcomes. No money moves; the decision comes back as the provider's
 * signed notification, like a real one.
 */
export async function TestCheckout({
  paymentId,
  token,
  payment,
  failed,
}: {
  paymentId: string;
  token: string;
  payment: TestPayment | null;
  failed: boolean;
}) {
  const t = await getTranslations("checkout");
  const format = await getFormatter();
  if (!payment) {
    return (
      <main className={styles.screen}>
        <StatePanel
          icon={<IconAlertTriangle stroke={1.75} />}
          tone="critical"
          role="alert"
          title={t("invalidTitle")}
          description={t("invalidDescription")}
        />
      </main>
    );
  }
  const amount = format.number(payment.amountKopecks / KOPECKS_IN_RUBLE, {
    style: "currency",
    currency: payment.currency,
    maximumFractionDigits: 2,
  });
  return (
    <main className={styles.screen}>
      <section className={styles.card} aria-labelledby="checkout-title">
        <header className={styles.header}>
          <span className={styles.provider}>
            <IconCreditCard stroke={1.75} aria-hidden />
            {t("provider")}
          </span>
          <span className={styles.test}>
            <IconFlask stroke={1.75} aria-hidden />
            {t("testMode")}
          </span>
        </header>
        <div className={styles.body}>
          <h1 id="checkout-title" className={styles.amount}>
            {amount}
          </h1>
          <p className={styles.description}>{payment.description}</p>
          <p className={styles.merchant}>
            {t("merchant")} <Brand />
          </p>
        </div>
        {failed ? (
          <Notice icon={<IconAlertTriangle stroke={1.75} />} tone="critical" role="alert">
            {t("failed")}
          </Notice>
        ) : null}
        <form
          className={styles.actions}
          method="post"
          action={`/pay/test/${encodeURIComponent(paymentId)}/decision`}
        >
          <input type="hidden" name="token" value={token} />
          <Button type="submit" name="decision" value="pay" variant="primary" block>
            {t("pay", { amount })}
          </Button>
          <Button type="submit" name="decision" value="decline" variant="secondary" block>
            {t("decline")}
          </Button>
        </form>
        <p className={styles.note}>{t("noMoney")}</p>
      </section>
    </main>
  );
}
