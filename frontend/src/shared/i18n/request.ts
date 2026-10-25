import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { LOCALE_COOKIE } from "./locales";
import { loadMessages } from "./messages";
import { resolveLocale } from "./negotiation";
import { TIME_ZONE } from "./time";

/** Every page is rendered in the visitor's language (see resolveLocale). */
export default getRequestConfig(async () => {
  const locale = resolveLocale({
    stored: (await cookies()).get(LOCALE_COOKIE)?.value,
    acceptLanguage: (await headers()).get("accept-language"),
  });
  return { locale, messages: await loadMessages(locale), timeZone: TIME_ZONE };
});
