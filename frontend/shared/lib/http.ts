/**
 * 后端 API 客户端：统一读取 NEXT_PUBLIC_API_BASE_URL，供页面按钮与数据加载使用。
 */

import {
  clearMaintenanceToken,
  getMaintenanceToken,
  notifyMaintenanceAuthExpired,
} from "@/features/auth/lib/token-store";
import { isDemoMode } from "@/shared/lib/demo-mode";
import {
  demoWorkbenchOverview,
  demoSystemMetrics,
  demoHealth,
  demoMaintenanceHistory,
  demoCasesList,
  demoCaseDetail,
  demoTaskDetail,
} from "@/features/dashboard/mock/workbench";

export function getApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}

const MAINTENANCE_AUTH_EXPIRED_MESSAGE = "登录已失效，请重新登录";
const MAINTENANCE_NETWORK_ERROR_MESSAGE = "无法连接检修后端，请确认服务已启动且地址可访问";

function normalizeMaintenanceNetworkError(error: unknown): Error {
  if (error instanceof Error) {
    const message = (error.message || "").trim();
    if (
      message === "Failed to fetch" ||
      message.includes("fetch failed") ||
      message.includes("NetworkError") ||
      message.includes("Load failed")
    ) {
      return new Error(MAINTENANCE_NETWORK_ERROR_MESSAGE);
    }
    return error;
  }
  return new Error(MAINTENANCE_NETWORK_ERROR_MESSAGE);
}

async function rawFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = `${getApiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: HeadersInit = { ...init?.headers };
  const h = headers as Record<string, string>;
  if (init?.body && !(init.body instanceof FormData) && !h["Content-Type"]) {
    h["Content-Type"] = "application/json";
  }
  return fetch(url, { ...init, headers: h });
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await rawFetch(path, init);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(text.slice(0, 400) || String(res.status));
  }
  return (text ? JSON.parse(text) : {}) as T;
}

/** 检修域标准响应包：{ success, data, message } */
export async function maintenanceJson<T>(path: string, init?: RequestInit, token?: string | null): Promise<T> {
  const t = token ?? getMaintenanceToken();
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string>) };
  if (t) headers.Authorization = `Bearer ${t}`;
  let res: Response;
  try {
    res = await rawFetch(path, { ...init, headers });
  } catch (error) {
    throw normalizeMaintenanceNetworkError(error);
  }
  const text = await res.text();
  let json: Record<string, unknown> = {};
  try {
    json = (text ? JSON.parse(text) : {}) as Record<string, unknown>;
  } catch {
    json = {};
  }
  if (!res.ok) {
    if (res.status === 401) {
      clearMaintenanceToken();
      notifyMaintenanceAuthExpired();
      throw new Error(MAINTENANCE_AUTH_EXPIRED_MESSAGE);
    }
    const detail = json.detail;
    const nestedDetailMessage =
      detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string"
        ? detail.message
        : null;
    const msg =
      (typeof json.message === "string" ? json.message : null) ||
      nestedDetailMessage ||
      (typeof detail === "string" ? detail : null) ||
      text.slice(0, 200);
    throw new Error(msg || String(res.status));
  }
  if (json && json.success === false) {
    throw new Error(typeof json.message === "string" ? json.message : "业务请求失败");
  }
  return (json?.data !== undefined ? json.data : json) as T;
}

export function isMaintenanceAuthExpiredError(error: unknown): boolean {
  return error instanceof Error && error.message === MAINTENANCE_AUTH_EXPIRED_MESSAGE;
}

// —— 通用只读 ——

export async function fetchHealth() {
  if (isDemoMode()) return demoHealth();
  return apiJson<{ status: string; database: string }>("/health");
}

export async function fetchSystemMetrics() {
  if (isDemoMode()) return demoSystemMetrics();
  return apiJson<Record<string, unknown>>("/api/v1/system/metrics");
}

export async function fetchWorkbenchOverview() {
  if (isDemoMode()) return demoWorkbenchOverview();
  return apiJson<WorkbenchOverview>("/api/v1/workbench/overview");
}

export async function fetchMaintenanceHistory(params?: { limit?: number; status?: string }) {
  if (isDemoMode()) return demoMaintenanceHistory();
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.status) sp.set("status", params.status);
  const q = sp.toString();
  return apiJson<MaintenanceTaskHistoryResponse>(`/api/v1/history${q ? `?${q}` : ""}`);
}

export async function fetchCasesList(params?: { limit?: number; status?: string }) {
  if (isDemoMode()) return demoCasesList();
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.status) sp.set("status", params.status);
  const q = sp.toString();
  return apiJson<MaintenanceCaseListResponse>(`/api/v1/cases${q ? `?${q}` : ""}`);
}

export async function fetchCaseDetail(caseId: number) {
  if (isDemoMode()) return demoCaseDetail(caseId);
  return apiJson<MaintenanceCaseDetail>(`/api/v1/cases/${caseId}`);
}

export async function deleteMaintenanceCase(caseId: number): Promise<void> {
  const res = await rawFetch(`/api/v1/cases/${caseId}`, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text.slice(0, 200) || String(res.status));
  }
}

/** 与后端 `MaintenanceCaseCreate` 对齐；须至少填写「处理步骤」或「处理结果总结」之一 */
export interface MaintenanceCaseCreatePayload {
  title: string;
  equipment_type: string;
  symptom_description: string;
  processing_steps?: string[];
  resolution_summary?: string | null;
  equipment_model?: string | null;
  fault_type?: string | null;
  work_order_id?: string | null;
  asset_code?: string | null;
  report_source?: string | null;
  priority?: "low" | "medium" | "high" | "urgent" | null;
  task_id?: number | null;
  attachment_name?: string | null;
  attachment_url?: string | null;
  knowledge_refs?: unknown[];
}

export async function createMaintenanceCase(body: MaintenanceCaseCreatePayload) {
  return apiJson<MaintenanceCaseDetail>(`/api/v1/cases`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchTaskDetail(taskId: number) {
  if (isDemoMode()) return demoTaskDetail(taskId);
  return apiJson<MaintenanceTaskDetail>(`/api/v1/tasks/${taskId}`);
}

export async function fetchTaskExport(taskId: number) {
  return apiJson<MaintenanceTaskExportPayload>(`/api/v1/export/${taskId}`);
}

export async function retryMaintenanceTask(taskId: number) {
  return apiJson<MaintenanceTaskDetail>(`/api/v1/tasks/${taskId}/retry`, {
    method: "POST",
  });
}

export async function saveMaintenanceTaskExecutionTimeline(
  taskId: number,
  events: Array<{ id: string; type: string; title: string; description: string; time: string }>,
  diagnosis_report?: string | null,
): Promise<void> {
  const res = await rawFetch(`/api/v1/tasks/${taskId}/execution-timeline`, {
    method: "PATCH",
    body: JSON.stringify({ events, diagnosis_report: diagnosis_report ?? null }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text.slice(0, 200) || String(res.status));
  }
}

/** 在浏览器中触发 JSON 文件下载（供「导出记录」等入口使用） */
export function downloadJsonInBrowser(filename: string, data: unknown) {
  if (typeof window === "undefined") return;
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.click();
  URL.revokeObjectURL(url);
}

export async function createMaintenanceTask(body: Record<string, unknown>) {
  return apiJson<MaintenanceTaskDetail>("/api/v1/tasks", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteMaintenanceTask(taskId: number): Promise<void> {
  const res = await rawFetch(`/api/v1/tasks/${taskId}`, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text.slice(0, 200) || String(res.status));
  }
}

/** Agent 协作同步接口返回（前端仅强类型消费常用字段） */
export interface AgentAssistResponse {
  run_id: string;
  status: string;
  summary: string;
  diagnosis_report?: string | null;
  diagnosis_structured?: {
    answer_mode?: "diagnosis" | "procedure";
    most_likely_fault: string;
    risk_level: string;
    confidence: number;
    main_symptoms: string[];
    preliminary_conclusion: string;
    next_steps: Array<
      | string
      | {
          step_no?: number | null;
          title: string;
          summary?: string;
          sections?: Array<{
            label: string;
            items: string[];
          }>;
          meta?: string[];
          raw_text?: string | null;
        }
    >;
    root_causes: Array<{ name: string; confidence: number; evidence: string }>;
    evidence_items: Array<{
      document_title: string;
      section?: string | null;
      excerpt?: string | null;
      source_name?: string | null;
      relevance_score?: number | null;
    }>;
    evidence_count: number;
    top_similarity?: number | null;
    work_order_ready: boolean;
  } | null;
  effective_query?: string | null;
  effective_keywords?: string[];
  knowledge_results?: Array<{
    chunk_id: number;
    document_id: number;
    title: string;
    source_name: string;
    excerpt: string;
  }>;
}

export async function postAgentAssist(body: Record<string, unknown>) {
  return apiJson<AgentAssistResponse>("/api/v1/agents/assist", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchKnowledgeDocuments(limit = 20) {
  return apiJson<KnowledgeDocumentListResponse>(`/api/v1/knowledge/documents?limit=${limit}`);
}

export async function fetchKnowledgeDocumentDetail(documentId: number) {
  return apiJson<KnowledgeDocumentDetail>(`/api/v1/knowledge/documents/${documentId}`);
}

export async function fetchKnowledgeDocumentChunks(documentId: number, limit = 8) {
  return apiJson<KnowledgeChunkPreviewResponse>(`/api/v1/knowledge/documents/${documentId}/chunks?limit=${limit}`);
}

export async function deleteKnowledgeDocument(documentId: number) {
  return apiJson<{ success: boolean; message: string }>(`/api/v1/knowledge/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function fetchKnowledgeImports(limit = 8) {
  return apiJson<KnowledgeImportListResponse>(`/api/v1/knowledge/imports?limit=${limit}`);
}

export async function deleteKnowledgeImportJob(jobId: number) {
  return apiJson<{ success: boolean; message: string }>(`/api/v1/knowledge/imports/${jobId}`, {
    method: "DELETE",
  });
}

export interface KnowledgeImportUploadPayload {
  file: File;
  equipment_type: string;
  title?: string;
  equipment_model?: string;
  fault_type?: string;
  section_reference?: string;
  source_type?: string;
  replace_existing?: boolean;
}

export async function importKnowledgeDocument(payload: KnowledgeImportUploadPayload) {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("equipment_type", payload.equipment_type);
  if (payload.title) form.append("title", payload.title);
  if (payload.equipment_model) form.append("equipment_model", payload.equipment_model);
  if (payload.fault_type) form.append("fault_type", payload.fault_type);
  if (payload.section_reference) form.append("section_reference", payload.section_reference);
  form.append("source_type", payload.source_type ?? "manual");
  form.append("replace_existing", String(Boolean(payload.replace_existing)));
  return apiJson<{ id: number; status: string; original_filename?: string }>("/api/v1/knowledge/imports", {
    method: "POST",
    body: form,
  });
}

/** 登录：返回 data 中的 access_token */
export async function maintenanceLogin(username: string, password: string) {
  const res = await rawFetch("/api/v1/maintenance/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  const text = await res.text();
  const json = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new Error(json?.message || text.slice(0, 200) || String(res.status));
  }
  const data = json?.data ?? json;
  if (!data?.access_token) throw new Error("登录响应缺少 access_token");
  return data as { access_token: string; token_type: string; user: { id: number; username: string } };
}

export async function listWorkOrders(token: string | null, page = 1, status?: string) {
  const sp = new URLSearchParams({ page: String(page), page_size: "50" });
  if (status) sp.set("status", status);
  return maintenanceJson<WorkOrderListPayload>(`/api/v1/maintenance/work-orders?${sp.toString()}`, {}, token);
}

export interface MaintenanceWorkOrderCreatePayload {
  device_id: number;
  maintenance_level?: string;
  source_task_id?: number;
}

export async function createWorkOrder(
  token: string | null,
  body: MaintenanceWorkOrderCreatePayload,
) {
  return maintenanceJson<Record<string, unknown>>(
    "/api/v1/maintenance/work-orders",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export interface WorkOrderDetailPayload extends WorkOrderItem {
  step_progress_json?: Record<string, unknown> | null;
  source_task?: {
    task_id: number;
    title?: string | null;
    diagnosis_report?: string | null;
    advice_card?: string | null;
    status?: string | null;
  } | null;
  device?: {
    id: number;
    asset_code?: string | null;
    model?: string | null;
    device_type?: string | null;
  };
  flow_template?: {
    id: number;
    name: string;
    steps_json: unknown;
  };
}

export interface WorkOrderEventItem {
  id: number;
  from_status?: string | null;
  to_status: string;
  event_type: string;
  payload?: Record<string, unknown> | null;
  actor_user_id?: number | null;
  created_at: string;
}

export interface WorkOrderMessageItem {
  id: number;
  role: string;
  content: string;
  retrieval_snapshot_id?: number | null;
  created_at: string;
}

export async function fetchWorkOrderDetail(token: string | null, workOrderId: number) {
  return maintenanceJson<WorkOrderDetailPayload>(`/api/v1/maintenance/work-orders/${workOrderId}`, {}, token);
}

export async function fetchWorkOrderEvents(token: string | null, workOrderId: number) {
  return maintenanceJson<{ items: WorkOrderEventItem[]; total: number; page: number; page_size: number }>(
    `/api/v1/maintenance/work-orders/${workOrderId}/events`,
    {},
    token,
  );
}

export async function fetchWorkOrderMessages(token: string | null, workOrderId: number, page = 1, pageSize = 50) {
  const sp = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return maintenanceJson<{ items: WorkOrderMessageItem[]; total: number; page: number; page_size: number }>(
    `/api/v1/maintenance/work-orders/${workOrderId}/messages?${sp.toString()}`,
    {},
    token,
  );
}

export async function postWorkOrderMessage(
  token: string | null,
  workOrderId: number,
  body: { content: string },
) {
  return maintenanceJson<{ id: number; created_at: string }>(
    `/api/v1/maintenance/work-orders/${workOrderId}/messages`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export async function enterWorkOrderMaintenance(token: string | null, workOrderId: number) {
  return maintenanceJson<Record<string, unknown>>(
    `/api/v1/maintenance/work-orders/${workOrderId}/actions/enter-maintenance`,
    { method: "POST" },
    token,
  );
}

export async function completeWorkOrderMaintenance(token: string | null, workOrderId: number) {
  return maintenanceJson<Record<string, unknown>>(
    `/api/v1/maintenance/work-orders/${workOrderId}/actions/complete-maintenance`,
    { method: "POST" },
    token,
  );
}

export interface MaintenanceAttachmentUploadPayload {
  file: File;
  biz_type: string;
  work_order_id?: number | null;
}

export interface MaintenanceAttachmentItem {
  id: number;
  work_order_id?: number | null;
  biz_type: string;
  mime_type?: string | null;
  size_bytes?: number | null;
  created_at?: string | null;
}

export async function uploadMaintenanceAttachment(
  token: string | null,
  payload: MaintenanceAttachmentUploadPayload,
) {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("biz_type", payload.biz_type);
  if (payload.work_order_id != null) {
    form.append("work_order_id", String(payload.work_order_id));
  }
  return maintenanceJson<MaintenanceAttachmentItem>(
    "/api/v1/maintenance/attachments",
    {
      method: "POST",
      body: form,
    },
    token,
  );
}

export interface WorkOrderFillingPayload {
  resolution_status: "resolved" | "unresolved";
  closure_code: "NORMAL" | "PART_REPLACED" | "ADJUSTED" | "OTHER" | "UNRESOLVED";
  attachment_ids: number[];
  detail_notes?: string | null;
  post_unresolved_action?: "REOPEN_ESCALATION" | "RETRY_RETRIEVAL" | "CLOSE_UNRESOLVED" | null;
  unresolved_reason_code?: "EQUIPMENT_LIMIT" | "INFO_INSUFFICIENT" | "EXPERT_REQUIRED" | "USER_ABORT" | "OTHER" | null;
}

export async function submitWorkOrderFilling(
  token: string | null,
  workOrderId: number,
  body: WorkOrderFillingPayload,
) {
  return maintenanceJson<{ work_order: Record<string, unknown>; filling_id: number }>(
    `/api/v1/maintenance/work-orders/${workOrderId}/fillings`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export async function confirmWorkOrderStep(
  token: string | null,
  workOrderId: number,
  body: { step_no: number; mark_done: true },
) {
  return maintenanceJson<Record<string, unknown>>(
    `/api/v1/maintenance/work-orders/${workOrderId}/steps/confirm`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export async function runWorkOrderRetrieval(
  token: string | null,
  workOrderId: number,
  body: { query_text?: string; maintenance_level?: string | null },
) {
  return maintenanceJson<{
    retrieval_snapshot_id: number;
    message_id: number;
    suggested_reply: string;
    citations: Array<{
      citation_label: string;
      chunk_id: number;
      source_document: string;
      section_reference?: string | null;
      page_reference?: string | null;
      excerpt?: string | null;
    }>;
    work_order: WorkOrderItem;
  }>(
    `/api/v1/maintenance/work-orders/${workOrderId}/retrieval`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export async function deleteWorkOrder(token: string | null, workOrderId: number): Promise<void> {
  const t = token ?? getMaintenanceToken();
  const headers: Record<string, string> = {};
  if (t) headers.Authorization = `Bearer ${t}`;
  let res: Response;
  try {
    res = await rawFetch(`/api/v1/maintenance/work-orders/${workOrderId}`, {
      method: "DELETE",
      headers,
    });
  } catch (error) {
    throw normalizeMaintenanceNetworkError(error);
  }
  if (!res.ok) {
    if (res.status === 401) {
      clearMaintenanceToken();
      notifyMaintenanceAuthExpired();
      throw new Error(MAINTENANCE_AUTH_EXPIRED_MESSAGE);
    }
    const text = await res.text();
    let message = text.slice(0, 200);
    try {
      const json = text ? JSON.parse(text) : {};
      message =
        json?.message ||
        json?.detail?.message ||
        (typeof json?.detail === "string" ? json.detail : null) ||
        message;
    } catch {}
    throw new Error(message || String(res.status));
  }
}

export interface MaintenanceDeviceItem {
  id: number;
  device_type: string;
  model: string;
  asset_code: string;
  location?: string | null;
}

export async function listMaintenanceDevices(token: string | null, page = 1) {
  const sp = new URLSearchParams({ page: String(page), page_size: "50" });
  return maintenanceJson<{ items: MaintenanceDeviceItem[]; total: number; page: number; page_size: number }>(
    `/api/v1/maintenance/devices?${sp.toString()}`,
    {},
    token,
  );
}

export interface MaintenanceDeviceCreatePayload {
  device_type: string;
  model: string;
  asset_code?: string | null;
  location?: string | null;
  responsibility_expert_user_id?: number | null;
}

export async function createMaintenanceDevice(
  token: string | null,
  body: MaintenanceDeviceCreatePayload,
) {
  return maintenanceJson<MaintenanceDeviceItem>(
    "/api/v1/maintenance/devices",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export async function fetchMaintenanceHealth() {
  return maintenanceJson<Record<string, unknown>>("/api/v1/maintenance/health", {}, null);
}

/** 顶栏图标等：轻量确认后端可达 */
export async function pingBackendReadiness() {
  await fetchSystemMetrics();
}

// —— 类型（仅前端消费字段） ——

export interface WorkbenchOverview {
  generated_at: string;
  stats: { key: string; label: string; value: number; accent: string }[];
  featured_queries: string[];
  agent_capabilities: string[];
  recent_tasks: WorkbenchTaskSummary[];
  recent_cases: WorkbenchCaseSummary[];
}

export interface WorkbenchTaskSummary {
  id: number;
  title: string;
  work_order_id: string | null;
  asset_code: string | null;
  equipment_type: string;
  equipment_model: string | null;
  maintenance_level: string;
  status: string;
  total_steps: number;
  completed_steps: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface WorkbenchCaseSummary {
  id: number;
  title: string;
  status: string;
  equipment_type: string;
  updated_at: string | null;
}

export interface MaintenanceTaskHistoryResponse {
  total: number;
  tasks: MaintenanceTaskHistoryItem[];
}

export interface MaintenanceTaskHistoryItem {
  id: number;
  title: string;
  equipment_type: string;
  equipment_model: string | null;
  status: string;
  maintenance_level: string;
  total_steps: number;
  completed_steps: number;
  created_at: string | null;
  updated_at: string | null;
  run_started_at?: string | null;
  run_finished_at?: string | null;
}

export interface MaintenanceTaskDetail {
  id: number;
  title: string;
  work_order_id?: string | null;
  asset_code?: string | null;
  report_source?: string | null;
  priority?: string | null;
  equipment_type: string;
  equipment_model: string | null;
  maintenance_level: string;
  fault_type: string | null;
  symptom_description: string | null;
  status: string;
  execution_timeline?: Array<{
    id: string;
    type: string;
    title: string;
    description: string;
    time: string;
  }>;
  total_steps: number;
  completed_steps: number;
  advice_card: string | null;
  diagnosis_report?: string | null;
  diagnosis_structured?: {
    answer_mode?: "diagnosis" | "procedure";
    most_likely_fault: string;
    risk_level: string;
    confidence: number;
    main_symptoms: string[];
    preliminary_conclusion: string;
    next_steps: Array<
      | string
      | {
          step_no?: number | null;
          title: string;
          summary?: string;
          sections?: Array<{
            label: string;
            items: string[];
          }>;
          meta?: string[];
          raw_text?: string | null;
        }
    >;
    root_causes: Array<{ name: string; confidence: number; evidence: string }>;
    evidence_items: Array<{
      document_title: string;
      section?: string | null;
      excerpt?: string | null;
      source_name?: string | null;
      relevance_score?: number | null;
    }>;
    evidence_count: number;
    top_similarity?: number | null;
    work_order_ready: boolean;
  } | null;
  source_refs?: Array<{
    chunk_id: number;
    document_id: number;
    title: string;
    source_name: string;
    equipment_type?: string;
    section_reference?: string;
    section_path?: string;
    page_reference?: string;
    citation_label?: string;
    excerpt?: string;
    retrieval_score?: number | null;
    rerank_score?: number | null;
  }>;
  created_at: string | null;
  updated_at: string | null;
  run_started_at?: string | null;
  run_finished_at?: string | null;
  steps: Array<{
    id: number;
    step_order?: number;
    title: string;
    status: string;
    instruction?: string;
    confirmation_text?: string | null;
    risk_warning?: string | null;
    caution?: string | null;
    required_tools?: string[];
    required_materials?: string[];
    estimated_minutes?: number | null;
    started_at?: string | null;
    completed_at?: string | null;
    runtime_events?: Array<{
      id: string;
      type: string;
      title: string;
      description: string;
      time: string;
    }>;
    knowledge_refs?: Array<{
      chunk_id?: number;
      document_id?: number;
      title?: string;
      excerpt?: string;
    }>;
  }>;
}

export interface MaintenanceTaskExportPayload {
  task: MaintenanceTaskDetail;
  exported_at: string;
  export_summary: string;
}

export interface MaintenanceCaseListResponse {
  total: number;
  cases: MaintenanceCaseListItem[];
}

export interface MaintenanceCaseListItem {
  id: number;
  title: string;
  equipment_type: string;
  equipment_model?: string | null;
  fault_type?: string | null;
  report_source?: string | null;
  priority?: string | null;
  status: string;
  symptom_description: string;
  updated_at: string | null;
}

export interface MaintenanceCaseDetail {
  id: number;
  title: string;
  equipment_type: string;
  equipment_model: string | null;
  fault_type?: string | null;
  symptom_description: string;
  processing_steps: string[];
  resolution_summary: string | null;
  status: string;
  priority?: string | null;
  report_source?: string | null;
  work_order_id?: string | null;
  reviewer_name?: string | null;
  review_note?: string | null;
  reviewed_at?: string | null;
  knowledge_refs: Array<{ chunk_id?: number; document_id?: number; title?: string; source_name?: string; excerpt?: string; type?: string; id?: string | number }>;
  corrections?: Array<{
    id: number;
    correction_target: string;
    original_content: string | null;
    corrected_content: string;
    note: string | null;
    status: string;
    created_at: string;
  }>;
  created_at?: string | null;
  updated_at?: string | null;
}

export async function reviewMaintenanceCase(
  caseId: number,
  body: { action: "approve" | "reject"; reviewer_name?: string; review_note?: string },
) {
  return apiJson<MaintenanceCaseDetail>(`/api/v1/cases/${caseId}/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function addCaseCorrection(
  caseId: number,
  body: { correction_target: string; original_content?: string; corrected_content: string; note?: string },
) {
  return apiJson<MaintenanceCaseDetail>(`/api/v1/cases/${caseId}/corrections`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface GraphNode {
  id: string;
  kind: string;
  label: string;
  properties: Record<string, unknown>;
}
export interface GraphEdge {
  id: number;
  source: string;
  target: string;
  relation_type: string;
  notes: string | null;
  created_at: string;
}
export interface GraphResponse { nodes: GraphNode[]; edges: GraphEdge[] }
export interface GraphStatsResponse {
  total_nodes: number;
  total_edges: number;
  nodes_by_kind: Record<string, number>;
  edges_by_type: Record<string, number>;
}

export async function fetchKnowledgeGraph(params?: { relation_type?: string; kind?: string; limit?: number }) {
  const sp = new URLSearchParams();
  if (params?.relation_type) sp.set("relation_type", params.relation_type);
  if (params?.kind) sp.set("kind", params.kind);
  if (params?.limit) sp.set("limit", String(params.limit));
  const q = sp.toString();
  return apiJson<GraphResponse>(`/api/v1/knowledge/graph${q ? `?${q}` : ""}`);
}

export async function fetchKnowledgeGraphStats() {
  return apiJson<GraphStatsResponse>("/api/v1/knowledge/graph/stats");
}

export interface KnowledgeDocumentListResponse {
  total: number;
  documents: KnowledgeDocumentListItem[];
}

export interface KnowledgeDocumentListItem {
  id: number;
  title: string;
  source_name: string;
  source_type: string;
  equipment_type: string;
  equipment_model?: string | null;
  fault_type?: string | null;
  status: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentDetail extends KnowledgeDocumentListItem {
  section_reference?: string | null;
  page_reference?: string | null;
  content_excerpt?: string | null;
}

export interface KnowledgeChunkPreview {
  chunk_id: number;
  chunk_index: number;
  heading?: string | null;
  content: string;
  page_reference?: string | null;
  section_reference?: string | null;
  section_path?: string | null;
  step_anchor?: string | null;
  image_anchor?: string | null;
}

export interface KnowledgeChunkPreviewResponse {
  document_id: number;
  total: number;
  chunks: KnowledgeChunkPreview[];
}

export interface KnowledgeImportJob {
  id: number;
  import_type: string;
  processing_note?: string | null;
  title?: string | null;
  source_name: string;
  source_type: string;
  equipment_type: string;
  equipment_model?: string | null;
  fault_type?: string | null;
  section_reference?: string | null;
  replace_existing: boolean;
  status: string;
  page_count?: number | null;
  chunk_count?: number | null;
  document_id?: number | null;
  preview_excerpt?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeImportListResponse {
  total: number;
  jobs: KnowledgeImportJob[];
}

export interface WorkOrderListPayload {
  items: WorkOrderItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface WorkOrderItem {
  id: number;
  device_id: number;
  status: string;
  maintenance_level: string;
  current_step_no?: number | null;
  source_task_id?: number | null;
  created_at: string;
  updated_at: string;
}
