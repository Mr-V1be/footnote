import { getRequestConfig } from "next-intl/server";

import { DEFAULT_LOCALE, loadMessages } from "./messages";

/**
 * The interface is Russian-first. Locale negotiation is not exposed yet, but
 * every string already goes through the message catalogue, so adding a locale
 * is adding a catalogue file.
 */
export default getRequestConfig(async () => ({
  locale: DEFAULT_LOCALE,
  messages: await loadMessages(DEFAULT_LOCALE),
  timeZone: "Europe/Moscow",
}));
