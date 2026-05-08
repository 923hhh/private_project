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
        "fixed right-6 top-2 z-40",
        "inline-flex h-[56px] w-[28px] items-center rounded-full border p-[3px]",
        "backdrop-blur-[8px]",
        "transition-all duration-[250ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40",
        "shadow-[0_10px_24px_rgba(15,23,42,0.12)] hover:border-brand/55 hover:shadow-[0_0_16px_rgba(16,185,129,0.18)]",
      )}
      style={{
        background: isDark
          ? "rgba(2,8,23,0.82)"
          : "rgba(255,255,255,0.92)",
        borderColor: isDark
          ? "rgba(16,185,129,0.58)"
          : "rgba(15,23,42,0.18)",
      }}
    >
      <span
        aria-hidden
        className={cn(
          "pointer-events-none absolute left-1/2 -translate-x-1/2 text-[10px] font-medium tracking-[0.02em]",
          isDark ? "top-[6px] text-emerald-300/90" : "bottom-[6px] text-slate-500",
        )}
      >
        {isDark ? "夜" : "日"}
      </span>
      <span
        aria-hidden
        className={cn(
          "absolute left-1/2 -translate-x-1/2 inline-flex h-[22px] w-[22px] items-center justify-center rounded-full border",
          "transition-all duration-[250ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
          isDark ? "top-[31px]" : "top-[3px]",
        )}
        style={{
          background: isDark ? "#111827" : "#ffffff",
          borderColor: isDark
            ? "rgba(110,231,183,0.32)"
            : "rgba(15,23,42,0.14)",
          boxShadow: isDark
            ? "0 0 0 1px rgba(16,185,129,0.24), 0 0 10px rgba(16,185,129,0.18)"
            : "0 4px 12px rgba(15,23,42,0.16)",
        }}
      >
        {isDark ? (
          <Moon className="h-3.5 w-3.5 text-emerald-200" />
        ) : (
          <Sun className="h-3.5 w-3.5 text-amber-500" />
        )}
      </span>
    </button>,
    document.body,
  );
}

