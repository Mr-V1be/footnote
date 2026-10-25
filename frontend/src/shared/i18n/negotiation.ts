import { FALLBACK_LOCALE, isLocale, type Locale } from "./locales";

/** A supported language named by a language tag ("en-GB" is English), if any. */
function localeOfTag(tag: string): Locale | null {
  const primary = tag.trim().split(/[-_]/, 1)[0]?.toLowerCase();
  return isLocale(primary) ? primary : null;
}

function weightOf(parameters: string[]): number {
  for (const parameter of parameters) {
    const [name, value] = parameter.split("=").map((part) => part.trim());
    if (name?.toLowerCase() === "q") {
      const weight = Number(value);
      return Number.isFinite(weight) ? weight : 0;
    }
  }
  return 1;
}

/**
 * The supported language a browser's Accept-Language prefers most: by
 * weight, then by order; a language weighted 0 is refused.
 */
export function preferredLocale(acceptLanguage: string | null | undefined): Locale | null {
  if (!acceptLanguage) return null;
  let best: { locale: Locale; weight: number } | null = null;
  for (const range of acceptLanguage.split(",")) {
    const [tag = "", ...parameters] = range.split(";");
    const locale = localeOfTag(tag);
    const weight = weightOf(parameters);
    if (locale && weight > 0 && (!best || weight > best.weight)) best = { locale, weight };
  }
  return best?.locale ?? null;
}

/**
 * The language a page is shown in: the visitor's stored choice, else the
 * browser's language, else English.
 */
export function resolveLocale({
  stored,
  acceptLanguage,
}: {
  stored: string | null | undefined;
  acceptLanguage: string | null | undefined;
}): Locale {
  if (isLocale(stored)) return stored;
  return preferredLocale(acceptLanguage) ?? FALLBACK_LOCALE;
}
