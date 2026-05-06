"use client";

import { createContext, createElement, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type ThemePreference = "light" | "dark";
export type ResolvedTheme = "light" | "dark";

type UseAppThemeResult = {
  themePreference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setThemePreference: (t: ThemePreference) => void;
};

const THEME_STORAGE_KEY = "themePreference";

const AppThemeContext = createContext<UseAppThemeResult | null>(null);

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference;
}

function applyThemeClass(resolved: ResolvedTheme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
}

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>("dark");
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("light");

  useEffect(() => {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
    const stored: ThemePreference = raw === "light" || raw === "dark" ? raw : "dark";
    setThemePreferenceState(stored);
    const resolved = resolveTheme(stored);
    setResolvedTheme(resolved);
    applyThemeClass(resolved);
  }, []);

  useEffect(() => {
    const resolved = resolveTheme(themePreference);
    setResolvedTheme(resolved);
    applyThemeClass(resolved);
  }, [themePreference]);

  const setThemePreference = (next: ThemePreference) => {
    setThemePreferenceState(next);
    window.localStorage.setItem(THEME_STORAGE_KEY, next);
    const resolved = resolveTheme(next);
    setResolvedTheme(resolved);
    applyThemeClass(resolved);
  };

  const value = useMemo<UseAppThemeResult>(
    () => ({
      themePreference,
      resolvedTheme,
      setThemePreference,
    }),
    [themePreference, resolvedTheme],
  );

  return createElement(AppThemeContext.Provider, { value }, children);
}

export function useAppTheme(): UseAppThemeResult {
  const ctx = useContext(AppThemeContext);
  if (!ctx) {
    throw new Error("useAppTheme must be used within AppThemeProvider");
  }
  return ctx;
}

