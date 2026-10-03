import { IconAlertTriangle } from "@tabler/icons-react";
import { getTranslations } from "next-intl/server";

import { MethodologyView } from "@/features/methodology/MethodologyView";
import { Page } from "@/shared/ui/page/Page";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import type { PublicFacts } from "./data";

/** The methodology rendered from public data: no session, no client requests. */
export async function PublicMethodology({ facts }: { facts: PublicFacts }) {
  const t = await getTranslations("methodology");
  return (
    <Page spacing="lg">
      {facts.checks ? (
        <MethodologyView
          catalog={facts.checks}
          quality={facts.quality}
          kinds={facts.kinds?.kinds ?? []}
        />
      ) : (
        <StatePanel
          icon={<IconAlertTriangle stroke={1.75} />}
          tone="critical"
          role="alert"
          title={t("errorTitle")}
          description={t("errorDescription")}
        />
      )}
    </Page>
  );
}
