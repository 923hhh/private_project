import { PermissionPlaceholderPage } from "@/features/auth/components/permission-placeholder-page";

export default function AdminAuditLogsPage() {
  return (
    <PermissionPlaceholderPage
      title="审计日志"
      description="这里预留管理员查看关键操作记录、权限变更和工单审计流水的入口。"
      requiredRoles={["admin"]}
    />
  );
}

