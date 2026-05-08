/** 检修域 JWT；统一保持在当前会话内，避免长期持久化登录状态。 */
const KEY = "dachuang_maintenance_token";
export const MAINTENANCE_AUTH_EXPIRED_EVENT = "maintenance-auth-expired";
export const MAINTENANCE_AUTH_CHANGED_EVENT = "maintenance-auth-changed";

function notifyMaintenanceAuthChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(MAINTENANCE_AUTH_CHANGED_EVENT));
}

export function getMaintenanceToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY) || sessionStorage.getItem(KEY);
}

export function setMaintenanceToken(token: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(KEY, token);
  localStorage.removeItem(KEY);
  notifyMaintenanceAuthChanged();
}

export function clearMaintenanceToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY);
  sessionStorage.removeItem(KEY);
  notifyMaintenanceAuthChanged();
}

export function notifyMaintenanceAuthExpired(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(MAINTENANCE_AUTH_EXPIRED_EVENT));
}
