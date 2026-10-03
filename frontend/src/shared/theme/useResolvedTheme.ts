"use client";

import { useMediaQuery } from "@/shared/hooks/useMediaQuery";

import { useThemePreference } from "./ThemeContext";

/** The theme in effect: the person's choice, or the system's when they follow it. */
export function useResolvedTheme(): "light" | "dark" {
  const { theme } = useThemePreference();
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  if (theme === "system") return systemDark ? "dark" : "light";
  return theme;
}
