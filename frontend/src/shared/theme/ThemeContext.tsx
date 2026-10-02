"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { ThemePreference } from "./theme";
import { useTheme } from "./useTheme";

interface ThemeState {
  theme: ThemePreference;
  setTheme: (theme: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({
  initial,
  children,
}: {
  initial: ThemePreference;
  children: ReactNode;
}) {
  const [theme, setTheme] = useTheme(initial);
  return <ThemeContext value={{ theme, setTheme }}>{children}</ThemeContext>;
}

export function useThemePreference(): ThemeState {
  const state = useContext(ThemeContext);
  if (!state) throw new Error("useThemePreference must be used inside ThemeProvider");
  return state;
}
