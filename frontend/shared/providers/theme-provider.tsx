"use client";

import { AppThemeProvider } from "@/shared/theme/app-theme";

type ThemeProviderProps = {
  children: React.ReactNode;
  attribute?: string;
  defaultTheme?: string;
  enableSystem?: boolean;
  storageKey?: string;
  disableTransitionOnChange?: boolean;
};

export function ThemeProvider({ children }: ThemeProviderProps) {
  return <AppThemeProvider>{children}</AppThemeProvider>;
}

