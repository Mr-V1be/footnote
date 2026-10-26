export const THEME_COOKIE = "footnote_theme";
export const THEMES = ["system", "light", "dark"] as const;
export type ThemePreference = (typeof THEMES)[number];
/** One year: the preference outlives sessions. */
export const THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export function parseTheme(value: string | undefined): ThemePreference {
  return THEMES.find((theme) => theme === value) ?? "system";
}

/** `data-theme` is omitted for "system" so the CSS follows the OS setting. */
export function themeAttribute(theme: ThemePreference): "light" | "dark" | undefined {
  return theme === "system" ? undefined : theme;
}
