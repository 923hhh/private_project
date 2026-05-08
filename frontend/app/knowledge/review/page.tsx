import { PermissionPlaceholderPage } from "@/features/auth/components/permission-placeholder-page";

export default function KnowledgeReviewPage() {
  return (
    <PermissionPlaceholderPage
      title="知识审核"
      description="这里预留专家审核知识草稿、校正内容并决定是否进入发布流程的入口。"
      requiredRoles={["expert", "admin"]}
    />
  );
}
