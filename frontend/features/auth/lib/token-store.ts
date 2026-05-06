/** 检修域 JWT；勾选“记住登录状态”时写入 localStorage，否则写入 sessionStorage。 */
const KEY = "dachuang_maintenance_token";
export const MAINTENANCE_AUTH_EXPIRED_EVENT = "maintenance-auth-expired";

export function getMaintenanceToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY) || sessionStorage.getItem(KEY);
}

export function setMaintenanceToken(token: string, remember = false): void {
  if (typeof window === "undefined") return;
  if (remember) {
    localStorage.setItem(KEY, token);
    sessionStorage.removeItem(KEY);
    return;
  }
  sessionStorage.setItem(KEY, token);
  localStorage.removeItem(KEY);
}

export function clearMaintenanceToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY);
  sessionStorage.removeItem(KEY);
}

export function notifyMaintenanceAuthExpired(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(MAINTENANCE_AUTH_EXPIRED_EVENT));
}
