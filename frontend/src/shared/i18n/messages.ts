import type ru from "../../../messages/ru.json";

import type { Locale } from "./locales";

/** The Russian catalogue is the source: every other one has each of its keys. */
export type Messages = typeof ru;

const catalogues: Record<Locale, () => Promise<Messages>> = {
  en: async () => (await import("../../../messages/en.json")).default,
  ru: async () => (await import("../../../messages/ru.json")).default,
};

export function loadMessages(locale: Locale): Promise<Messages> {
  return catalogues[locale]();
}
