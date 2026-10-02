"use client";

import { useCallback, useState } from "react";

import { THEME_COOKIE, THEME_COOKIE_MAX_AGE, themeAttribute, type ThemePreference } from "./theme";

export function useTheme(
  initial: ThemePreference,
): [ThemePreference, (theme: ThemePreference) => void] {
  const [theme, setThemeState] = useState(initial);
  const setTheme = useCallback((next: ThemePreference) => {
    setThemeState(next);
    const attribute = themeAttribute(next);
    if (attribute) document.documentElement.dataset.theme = attribute;
    else delete document.documentElement.dataset.theme;
    document.cookie = `${THEME_COOKIE}=${next}; path=/; max-age=${THEME_COOKIE_MAX_AGE}; samesite=lax`;
  }, []);
  return [theme, setTheme];
}
