import { PermissionPlaceholderPage } from "@/features/auth/components/permission-placeholder-page";

export default function AdminUsersPage() {
  return (
    <PermissionPlaceholderPage
      title="用户管理"
      description="这里预留管理员账户、角色分配和人员维护入口。"
      requiredRoles={["admin"]}
    />
  );
}

