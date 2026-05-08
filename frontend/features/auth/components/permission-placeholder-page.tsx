"use client";

import Link from "next/link";

import { useMaintenanceAuth } from "@/features/auth/maintenance-auth";
import type { MaintenanceRole } from "@/shared/lib/http";
import { Header } from "@/shared/components/brand/app-header";

const roleLabelMap: Record<MaintenanceRole, string> = {
  worker: "检修员",
  expert: "专家",
  safety: "审批员",
  admin: "管理员",
};

export function PermissionPlaceholderPage({
  title,
  description,
  requiredRoles,
}: {
  title: string;
  description: string;
  requiredRoles: MaintenanceRole[];
}) {
  const { hasAnyRole, isLoading } = useMaintenanceAuth();
  const allowed = hasAnyRole(...requiredRoles);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="app-main app-main-wide">
        <div className="app-card p-6">
          <h1 className="text-xl font-semibold text-foreground">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
          <div className="mt-6 rounded-lg border border-border bg-muted/20 p-5 text-sm text-muted-foreground">
            {isLoading
              ? "正在校验当前账号权限..."
              : allowed
                ? "当前入口权限已就绪，后续可在这里继续补充完整的管理功能。"
                : `当前页面仅限 ${requiredRoles.map((role) => roleLabelMap[role]).join(" / ")} 使用。`}
          </div>
          <div className="mt-5">
            <Link href="/dashboard" className="app-btn-secondary">
              返回工作台
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

