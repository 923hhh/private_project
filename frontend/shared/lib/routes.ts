/**
 * 应用内主要路径（落地页 ↔ 控制台 ↔ 登录）
 */
export const ROUTES = {
  marketingHome: "/",
  marketingLanding: "/landing",
  dashboard: "/dashboard",
  login: "/login",
} as const;

/** 当前为独立 /landing 路由时，Logo 回到 /landing，否则回到首页 / */
export function marketingEntryHref(pathname: string | null | undefined): typeof ROUTES.marketingHome | typeof ROUTES.marketingLanding {
  return pathname === "/landing" ? ROUTES.marketingLanding : ROUTES.marketingHome;
}

/** 在当前营销路由下拼接锚点（首页 / 或 /landing） */
export function marketingHashHref(pathname: string | null | undefined, hash: string): string {
  const base = pathname === "/landing" ? ROUTES.marketingLanding : ROUTES.marketingHome;
  const h = hash.startsWith("#") ? hash : `#${hash}`;
  return `${base}${h}`;
}
