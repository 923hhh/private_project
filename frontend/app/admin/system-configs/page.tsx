import { PermissionPlaceholderPage } from "@/features/auth/components/permission-placeholder-page";

export default function AdminSystemConfigsPage() {
  return (
    <PermissionPlaceholderPage
      title="系统配置"
      description="这里预留系统热配置、阈值参数和检修域运行配置入口。"
      requiredRoles={["admin"]}
    />
  );
}

