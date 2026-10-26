/**
 * The interface languages. A new one is a new entry here and a catalogue in
 * `messages/` with every key of the Russian one.
 */
export const LOCALES = ["en", "ru"] as const;
export type Locale = (typeof LOCALES)[number];

/** For a visitor whose choice and browser name no supported language. */
export const FALLBACK_LOCALE: Locale = "en";

/**
 * The language of the documents the product checks and of the law it checks
 * them against. Their text is shown as it is, marked as such for assistive
 * technology, whatever the interface language.
 */
export const DOCUMENT_LOCALE: Locale = "ru";

/** Each language as its readers name it, whatever the interface shows. */
export const LOCALE_NAMES: Record<Locale, string> = { en: "English", ru: "Русский" };

export const LOCALE_COOKIE = "footnote_locale";
/** One year: the choice outlives sessions, like the theme. */
export const LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export function isLocale(value: unknown): value is Locale {
  return LOCALES.some((locale) => locale === value);
}
