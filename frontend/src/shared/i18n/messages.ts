import type ru from "../../../messages/ru.json";

export const LOCALES = ["ru"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "ru";

export type Messages = typeof ru;

const catalogues: Record<Locale, () => Promise<Messages>> = {
  ru: async () => (await import("../../../messages/ru.json")).default,
};

export function loadMessages(locale: Locale): Promise<Messages> {
  return catalogues[locale]();
}
