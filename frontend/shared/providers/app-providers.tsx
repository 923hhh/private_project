"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { toast, Toaster } from "sonner";
import { ThemeProvider } from "@/shared/providers/theme-provider";
import { ThemeToggle } from "@/shared/components/ui/theme-toggle";
import { MAINTENANCE_AUTH_EXPIRED_EVENT } from "@/features/auth/lib/token-store";
import { ROUTES } from "@/shared/lib/routes";

export function AppProviders({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const handleExpired = () => {
      const currentPath =
        typeof window !== "undefined" ? `${window.location.pathname}${window.location.search}` : pathname || ROUTES.dashboard;
      const next =
        currentPath && currentPath !== ROUTES.login
          ? `?next=${encodeURIComponent(currentPath)}&reason=expired`
          : "?reason=expired";
      toast.error("登录已失效，请重新登录");
      if (pathname !== ROUTES.login) {
        router.push(`${ROUTES.login}${next}`);
        router.refresh();
      }
    };

    window.addEventListener(MAINTENANCE_AUTH_EXPIRED_EVENT, handleExpired as EventListener);
    return () => {
      window.removeEventListener(MAINTENANCE_AUTH_EXPIRED_EVENT, handleExpired as EventListener);
    };
  }, [pathname, router]);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      storageKey="themePreference"
      disableTransitionOnChange
    >
      {children}
      <ThemeToggle />
      <Toaster
        position="top-right"
        richColors
        closeButton
        toastOptions={{
          duration: 2200,
        }}
      />
    </ThemeProvider>
  );
}

