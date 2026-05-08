"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";

import {
  MAINTENANCE_AUTH_CHANGED_EVENT,
  MAINTENANCE_AUTH_EXPIRED_EVENT,
  getMaintenanceToken,
} from "@/features/auth/lib/token-store";
import { fetchMaintenanceMe, type MaintenanceRole, type MaintenanceUser } from "@/shared/lib/http";

type MaintenanceAuthContextValue = {
  user: MaintenanceUser | null;
  roles: MaintenanceRole[];
  isLoggedIn: boolean;
  isLoading: boolean;
  hasRole: (role: MaintenanceRole) => boolean;
  hasAnyRole: (...roles: MaintenanceRole[]) => boolean;
  refreshUser: () => Promise<void>;
};

const MaintenanceAuthContext = createContext<MaintenanceAuthContextValue | null>(null);

export function MaintenanceAuthProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<MaintenanceUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = async () => {
    const token = getMaintenanceToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const payload = await fetchMaintenanceMe(token);
      setUser(payload);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshUser();
  }, [pathname]);

  useEffect(() => {
    const syncAuth = () => {
      void refreshUser();
    };
    const clearAuth = () => {
      setUser(null);
      setIsLoading(false);
    };

    window.addEventListener(MAINTENANCE_AUTH_CHANGED_EVENT, syncAuth as EventListener);
    window.addEventListener(MAINTENANCE_AUTH_EXPIRED_EVENT, clearAuth as EventListener);
    return () => {
      window.removeEventListener(MAINTENANCE_AUTH_CHANGED_EVENT, syncAuth as EventListener);
      window.removeEventListener(MAINTENANCE_AUTH_EXPIRED_EVENT, clearAuth as EventListener);
    };
  }, []);

  const value = useMemo<MaintenanceAuthContextValue>(() => {
    const roles = Array.isArray(user?.roles) ? user.roles : [];
    return {
      user,
      roles,
      isLoggedIn: Boolean(user),
      isLoading,
      hasRole: (role) => roles.includes(role),
      hasAnyRole: (...requestedRoles) => requestedRoles.some((role) => roles.includes(role)),
      refreshUser,
    };
  }, [isLoading, user]);

  return <MaintenanceAuthContext.Provider value={value}>{children}</MaintenanceAuthContext.Provider>;
}

export function useMaintenanceAuth() {
  const ctx = useContext(MaintenanceAuthContext);
  if (!ctx) {
    throw new Error("useMaintenanceAuth must be used within MaintenanceAuthProvider");
  }
  return ctx;
}

