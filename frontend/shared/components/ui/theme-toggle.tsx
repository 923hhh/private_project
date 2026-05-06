"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { createPortal } from "react-dom";
import { useAppTheme } from "@/shared/theme/app-theme";
import { cn } from "@/shared/lib/utils";

export function ThemeToggle() {
  const { themePreference, setThemePreference } = useAppTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = themePreference === "dark";

  if (!mounted) {
    return null;
  }

  return createPortal(
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label="切换浅色/深色模式"
      title={isDark ? "切换到浅色模式" : "切换到深色模式"}
      onClick={() => setThemePreference(isDark ? "light" : "dark")}
      className={cn(
        "fixed right-6 top-[82px] z-40",
        "inline-flex h-[56px] w-[28px] items-center rounded-full border p-[3px]",
        "backdrop-blur-[8px]",
        "transition-all duration-[250ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
        "hover:border-brand/45 hover:shadow-[0_0_12px_rgba(16,185,129,0.12)]",
      )}
      style={{
        background: isDark
          ? "rgba(16,185,129,0.12)"
          : "rgba(15,23,42,0.04)",
        borderColor: isDark
          ? "rgba(16,185,129,0.35)"
          : "rgba(15,23,42,0.14)",
      }}
    >
      <span
        aria-hidden
        className={cn(
          "absolute left-1/2 -translate-x-1/2 inline-flex h-[22px] w-[22px] items-center justify-center rounded-full border",
          "transition-all duration-[250ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
          isDark ? "top-[31px]" : "top-[3px]",
        )}
        style={{
          background: isDark ? "#0f172a" : "#ffffff",
          borderColor: isDark
            ? "rgba(255,255,255,0.08)"
            : "rgba(15,23,42,0.10)",
          boxShadow: isDark
            ? "0 0 0 1px rgba(16,185,129,0.18), 0 0 8px rgba(16,185,129,0.12)"
            : "0 2px 6px rgba(15,23,42,0.10)",
        }}
      >
        {isDark ? (
          <Moon className="h-3 w-3 text-slate-300 opacity-75" />
        ) : (
          <Sun className="h-3 w-3 text-amber-500 opacity-80" />
        )}
      </span>
    </button>,
    document.body,
  );
}

