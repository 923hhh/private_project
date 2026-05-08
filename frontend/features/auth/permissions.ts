import type { MaintenanceRole, MaintenanceUser } from "@/shared/lib/http";

const WORK_ORDER_ROLES: MaintenanceRole[] = ["worker", "expert", "admin"];
const APPROVAL_ROLES: MaintenanceRole[] = ["safety", "admin"];
const ACCEPTANCE_ROLES: MaintenanceRole[] = ["expert", "admin"];
const ADMIN_ROLES: MaintenanceRole[] = ["admin"];
const KNOWLEDGE_REVIEW_ROLES: MaintenanceRole[] = ["expert"];
const ASSIGNMENT_ROLES: MaintenanceRole[] = ["admin", "expert"];

export function hasRole(user: MaintenanceUser | null | undefined, role: MaintenanceRole) {
  return Array.isArray(user?.roles) && user.roles.includes(role);
}

export function hasAnyRole(user: MaintenanceUser | null | undefined, roles: MaintenanceRole[]) {
  return roles.some((role) => hasRole(user, role));
}

export function canOperateWorkOrder(user: MaintenanceUser | null | undefined) {
  return hasAnyRole(user, WORK_ORDER_ROLES);
}

export function canEnterMaintenance(user: MaintenanceUser | null | undefined, status?: string | null) {
  return canOperateWorkOrder(user) && ["S1", "S3", "S5"].includes(String(status || "").toUpperCase());
}

export function canCompleteMaintenance(user: MaintenanceUser | null | undefined, status?: string | null) {
  return canOperateWorkOrder(user) && String(status || "").toUpperCase() === "S7";
}

export function canSubmitFilling(user: MaintenanceUser | null | undefined, status?: string | null) {
  return canOperateWorkOrder(user) && String(status || "").toUpperCase() === "S8";
}

export function canConfirmWorkOrderStep(user: MaintenanceUser | null | undefined, status?: string | null) {
  return canOperateWorkOrder(user) && String(status || "").toUpperCase() === "S7";
}

export function canAcceptFillReview(user: MaintenanceUser | null | undefined, status?: string | null) {
  return hasAnyRole(user, ACCEPTANCE_ROLES) && String(status || "").toUpperCase() === "S9";
}

export function canCreateKnowledgeDraft(user: MaintenanceUser | null | undefined, status?: string | null) {
  return hasAnyRole(user, ACCEPTANCE_ROLES) && String(status || "").toUpperCase() === "S10";
}

export function canResolveApproval(user: MaintenanceUser | null | undefined) {
  return hasAnyRole(user, APPROVAL_ROLES);
}

export function canAccessKnowledgeReview(user: MaintenanceUser | null | undefined) {
  return hasAnyRole(user, KNOWLEDGE_REVIEW_ROLES);
}

export function canAccessKnowledgePublish(user: MaintenanceUser | null | undefined) {
  return hasAnyRole(user, ADMIN_ROLES);
}

export function canAccessAdmin(user: MaintenanceUser | null | undefined) {
  return hasAnyRole(user, ADMIN_ROLES);
}

export function canDeleteWorkOrder(user: MaintenanceUser | null | undefined) {
  return hasAnyRole(user, ADMIN_ROLES);
}

export function canAssignWorkOrder(user: MaintenanceUser | null | undefined) {
  return hasAnyRole(user, ASSIGNMENT_ROLES);
}
