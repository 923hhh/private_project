"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Activity,
  CheckCircle2,
  ChevronLeft,
  FileText,
  Loader2,
  MessageSquare,
  PenTool,
  RefreshCw,
  Send,
  Wrench,
} from "lucide-react";
import { Header } from "@/shared/components/brand/app-header";
import { getMaintenanceToken } from "@/features/auth/lib/token-store";
import { createMaintenanceCase } from "@/features/cases/api";
import { fetchTaskDetail, type MaintenanceTaskDetail } from "@/features/tasks/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import {
  completeWorkOrderMaintenance,
  confirmWorkOrderStep,
  enterWorkOrderMaintenance,
  fetchWorkOrderDetail,
  fetchWorkOrderEvents,
  fetchWorkOrderMessages,
  isMaintenanceAuthExpiredError,
  postWorkOrderMessage,
  submitWorkOrderFilling,
  type WorkOrderDetailPayload,
  type WorkOrderEventItem,
  type WorkOrderMessageItem,
  uploadMaintenanceAttachment,
} from "@/features/tickets/api";
import { formatDateTimeLocal } from "@/shared/lib/utils";

const maintenanceLevelMeta: Record<
  string,
  { label: string; className: string }
> = {
  emergency: {
    label: "紧急检修",
    className: "border-red-500/30 bg-red-500/15 text-red-400",
  },
  standard: {
    label: "标准检修",
    className: "border-orange-500/30 bg-orange-500/15 text-orange-400",
  },
  routine: {
    label: "例行检修",
    className: "border-blue-500/30 bg-blue-500/15 text-blue-400",
  },
};

const workOrderStatusMeta: Record<
  string,
  { label: string; className: string }
> = {
  S1: { label: "已创建", className: "border-sky-500/30 bg-sky-500/15 text-sky-500" },
  S2: { label: "检索处理中", className: "border-indigo-500/30 bg-indigo-500/15 text-indigo-500" },
  S3: { label: "待检修", className: "border-amber-500/30 bg-amber-500/15 text-amber-500" },
  S4: { label: "会诊处理中", className: "border-violet-500/30 bg-violet-500/15 text-violet-500" },
  S5: { label: "待进场", className: "border-cyan-500/30 bg-cyan-500/15 text-cyan-500" },
  S6: { label: "待审批", className: "border-orange-500/30 bg-orange-500/15 text-orange-500" },
  S7: { label: "检修中", className: "border-emerald-500/30 bg-emerald-500/15 text-emerald-500" },
  S8: { label: "待回填", className: "border-blue-500/30 bg-blue-500/15 text-blue-500" },
  S9: { label: "待验收", className: "border-yellow-500/30 bg-yellow-500/15 text-yellow-500" },
  S10: { label: "已完成", className: "border-emerald-500/30 bg-emerald-500/15 text-emerald-500" },
  SX: { label: "已终止", className: "border-red-500/30 bg-red-500/15 text-red-500" },
};

const eventLabelMap: Record<string, string> = {
  work_order_created: "工单创建",
  retrieval_started: "知识检索开始",
  retrieval_done: "知识检索完成",
  enter_maintenance: "进入检修",
  complete_maintenance: "完成检修",
  escalation_created: "发起升级会诊",
  escalation_resolved: "升级会诊完成",
  approval_approved: "审批通过",
  approval_rejected: "审批驳回",
  expert_accept_fill: "专家验收通过",
  fill_submitted: "已提交回填",
};

type TimelineEntry =
  | {
      id: string;
      kind: "event";
      title: string;
      content: string;
      time: string;
      actor: string;
    }
  | {
      id: string;
      kind: "message";
      title: string;
      content: string;
      time: string;
      actor: string;
    };

function getMaintenanceLevelMeta(level?: string | null) {
  return maintenanceLevelMeta[String(level || "").toLowerCase()] ?? {
    label: level || "未分级",
    className: "border-slate-500/30 bg-slate-500/15 text-slate-500 dark:text-slate-400",
  };
}

function getWorkOrderStatusMeta(status?: string | null) {
  return workOrderStatusMeta[String(status || "").toUpperCase()] ?? {
    label: status || "未知状态",
    className: "border-slate-500/30 bg-slate-500/15 text-slate-500 dark:text-slate-400",
  };
}

function formatWorkOrderCode(id: number) {
  return `WO-${String(id).padStart(6, "0")}`;
}

function parseReferenceTitles(text: string) {
  return Array.from(text.matchAll(/\[[^\]]+\]\s*([^（(;；\n]+)/g))
    .map((match) => match[1]?.trim())
    .filter(Boolean);
}

function summarizeAssistantMessage(text: string | null | undefined) {
  const raw = String(text || "").trim();
  if (!raw) return "系统已生成一条检修建议。";
  if (raw.startsWith("优先沿用来源诊断建议：")) {
    return "已优先承接来源诊断结果，并生成本工单的执行建议。";
  }
  if (raw.startsWith("优先依据诊断结论推进检修：")) {
    return "已根据来源诊断结论生成本工单的执行建议。";
  }
  if (raw.startsWith("建议参考：")) {
    const titles = parseReferenceTitles(raw);
    if (titles.length === 0) {
      return "系统已匹配到可参考的检修资料。";
    }
    const uniqueTitles = Array.from(new Set(titles));
    const preview = uniqueTitles.slice(0, 3).join("、");
    return `系统已匹配 ${titles.length} 条参考资料，主要包括：${preview}${uniqueTitles.length > 3 ? " 等" : ""}。`;
  }
  return raw;
}

function formatTimelineActor(entry: { actor_user_id?: number | null; role?: string; event_type?: string }) {
  if (entry.role === "assistant") return "系统助手";
  if (entry.role) return "现场人员";
  if (entry.event_type === "work_order_created") return entry.actor_user_id ? `创建人 #${entry.actor_user_id}` : "创建人";
  return entry.actor_user_id ? `操作人 #${entry.actor_user_id}` : "系统";
}

function formatEventContent(event: WorkOrderEventItem) {
  const fromLabel = getWorkOrderStatusMeta(event.from_status).label;
  const toLabel = getWorkOrderStatusMeta(event.to_status).label;

  switch (event.event_type) {
    case "work_order_created":
      return "系统已创建检修工单，等待生成可执行的检修流程。";
    case "retrieval_started":
      return "系统开始检索相关知识和历史案例，正在整理可参考的处理步骤。";
    case "retrieval_done":
      return "知识检索已完成，系统已生成可参考的检修建议，可继续进入检修。";
    case "enter_maintenance":
      return "工单已进入现场检修阶段，可按步骤执行并逐项确认。";
    case "complete_maintenance":
      return "现场检修已结束，等待补充处理结果或后续回填。";
    case "fill_submitted":
      return "检修结果已提交，等待进一步验收。";
    case "approval_approved":
      return "审批已通过，可继续执行后续流程。";
    case "approval_rejected":
      return "审批未通过，请根据意见补充信息后再提交。";
    case "approval_need_info":
      return "当前流程需要补充更多信息后才能继续。";
    case "expert_accept_fill":
      return "专家已确认本次检修结果，工单流程完成。";
    case "escalation_created":
      return "已发起升级会诊，等待专家进一步介入。";
    case "escalation_resolved":
      return "升级会诊已处理完成，可回到当前工单继续推进。";
    default:
      if (event.from_status || event.to_status) {
        return `工单状态已从“${fromLabel}”更新为“${toLabel}”。`;
      }
      return eventLabelMap[event.event_type] || "流程已更新。";
  }
}

function buildTitle(detail: WorkOrderDetailPayload | null) {
  if (!detail) return "工单详情";
  const device = detail.device;
  if (!device) return `${formatWorkOrderCode(detail.id)} 检修工单`;
  const primary = device.asset_code || device.model || device.device_type || formatWorkOrderCode(detail.id);
  return `${primary} 检修工单`;
}

function buildSummary(
  detail: WorkOrderDetailPayload | null,
  messages: WorkOrderMessageItem[],
  events: WorkOrderEventItem[],
) {
  const latestAssistantMessage = [...messages]
    .reverse()
    .find((item) => item.role === "assistant" && item.content?.trim());
  if (latestAssistantMessage) {
    return summarizeAssistantMessage(latestAssistantMessage.content);
  }
  const latestEvent = [...events].reverse()[0];
  if (latestEvent) return formatEventContent(latestEvent);
  if (detail?.status) {
    return `当前工单已进入${getWorkOrderStatusMeta(detail.status).label}阶段。`;
  }
  if (detail?.device) {
    return `当前工单已绑定设备 ${detail.device.device_type || "设备"}${detail.device.model ? ` · ${detail.device.model}` : ""}。`;
  }
  return "当前工单暂无更多过程说明。";
}

function parseActionSteps(text: string | null | undefined) {
  const raw = String(text || "").trim();
  if (!raw) return [];

  const normalizedLines = raw
    .split("\n")
    .map((line) => line.replace(/^[\-•●■\d．。、)\s]+/, "").trim())
    .filter(Boolean)
    .filter(
      (line) =>
        !line.startsWith("已优先承接来源诊断结果") &&
        !line.startsWith("优先沿用来源诊断建议") &&
        !line.startsWith("优先依据诊断结论推进检修") &&
        !line.startsWith("本次优先参考来源诊断已命中的知识依据") &&
        !line.startsWith("依据："),
    );

  const preferred = normalizedLines.filter((line) => line.length > 4);
  if (preferred.length > 0) {
    return preferred.slice(0, 5);
  }

  return raw
    .split(/[；;。]/)
    .map((part) => part.replace(/^[\-•●■\d．。、)\s]+/, "").trim())
    .filter(Boolean)
    .slice(0, 5);
}

function buildActionCards(text: string | null | undefined) {
  return parseActionSteps(text).map((step, index) => {
    const parts = step
      .split(/[，,:：]/)
      .map((part) => part.trim())
      .filter(Boolean);

    const title = parts[0] || `建议动作 ${index + 1}`;
    const detail = parts.slice(1).join("，");
    const hint =
      parts.find((part) => /检查|确认|记录|观察|复核|排查|断开|测量/.test(part)) ||
      "";

    return {
      id: `${index}-${title}`,
      order: index + 1,
      title,
      detail: detail && detail !== title ? detail : "",
      hint,
    };
  });
}

function parseStructuredLines(text: string | null | undefined) {
  const raw = String(text || "").trim();
  if (!raw) {
    return { summary: "", items: [] as string[] };
  }

  const cleaned = raw.replace(/\s+/g, " ").trim();
  const lineItems = raw
    .split("\n")
    .map((line) => line.replace(/^[\-•●■\d．。、)\s]+/, "").trim())
    .filter(Boolean);

  const sentenceItems = cleaned
    .split(/[；;。]/)
    .map((part) => part.replace(/^[\-•●■\d．。、)\s]+/, "").trim())
    .filter(Boolean);

  const items = (lineItems.length > 1 ? lineItems : sentenceItems).slice(0, 4);
  const summary = items[0] || cleaned.slice(0, 120);
  const detailItems = items.slice(1);

  return { summary, items: detailItems };
}

function matchFirstByKeywords(items: string[], keywords: string[]) {
  return items.find((item) => keywords.some((keyword) => item.includes(keyword))) || "";
}

function buildActionCardsFromTask(
  taskDetail: MaintenanceTaskDetail | null,
  fallbackText: string | null | undefined,
  assistantSuggestionText?: string | null,
) {
  const assistantSteps = buildActionCards(assistantSuggestionText);
  if (assistantSteps.length > 0) {
    return assistantSteps.map((step, index) => ({
      ...step,
      order: index + 1,
    }));
  }

  const nextSteps = taskDetail?.diagnosis_structured?.next_steps ?? [];
  const structuredSteps = nextSteps
    .map((step, index) => {
      if (typeof step === "string") {
        const text = step.trim();
        if (!text) return null;
        return {
          id: `legacy-${index}-${text}`,
          order: index + 1,
          title: text,
          detail: text,
          hint: "",
        };
      }
      const title = step.title?.trim() || `建议动作 ${index + 1}`;
      const detail = (step.summary || step.raw_text || title).trim();
      const hint = step.meta?.[0] || "";
      return {
        id: `structured-${index}-${title}`,
        order: Number(step.step_no) || index + 1,
        title,
        detail,
        hint,
      };
    })
    .filter((item): item is { id: string; order: number; title: string; detail: string; hint: string } => Boolean(item));

  if (structuredSteps.length > 0) {
    return structuredSteps.map((step, index) => ({
      ...step,
      order: index + 1,
      detail: step.detail && step.detail !== step.title ? step.detail : "",
    }));
  }

  return buildActionCards(fallbackText);
}

function buildDiagnosisConclusionFromTask(
  taskDetail: MaintenanceTaskDetail | null,
  fallbackDiagnosisText: string | null | undefined,
) {
  const structured = taskDetail?.diagnosis_structured;
  if (!structured) {
    const diagnosis = parseStructuredLines(fallbackDiagnosisText);
    return (
      matchFirstByKeywords(
        [diagnosis.summary, ...diagnosis.items].filter(Boolean),
        ["判断", "结论", "异常", "故障", "定位"],
      ) ||
      diagnosis.summary ||
      "当前未形成明确结论。"
    );
  }

  return (
    structured.preliminary_conclusion?.trim() ||
    structured.most_likely_fault?.trim() ||
    "当前未形成明确结论。"
  );
}

function buildTimeline(
  events: WorkOrderEventItem[],
  messages: WorkOrderMessageItem[],
): TimelineEntry[] {
  const entries: Array<TimelineEntry & { sortKey: number }> = [];

  for (const event of events) {
    const ts = Date.parse(String(event.created_at || ""));
    const payloadText =
      event.payload && Object.keys(event.payload).length > 0
        ? JSON.stringify(event.payload, null, 0)
        : "";
    entries.push({
      id: `event-${event.id}`,
      kind: "event",
      title: eventLabelMap[event.event_type] || event.event_type,
      content: formatEventContent(event),
      time: formatDateTimeLocal(event.created_at),
      actor: formatTimelineActor(event),
      sortKey: Number.isNaN(ts) ? 0 : ts,
    });
  }

  for (const message of messages) {
    const ts = Date.parse(String(message.created_at || ""));
    entries.push({
      id: `message-${message.id}`,
      kind: "message",
      title: message.role === "assistant" ? "智能建议" : "工单留言",
      content: message.role === "assistant" ? summarizeAssistantMessage(message.content) : message.content,
      time: formatDateTimeLocal(message.created_at),
      actor: formatTimelineActor(message),
      sortKey: Number.isNaN(ts) ? 0 : ts,
    });
  }

  return entries.sort((a, b) => a.sortKey - b.sortKey);
}

function TimelineCard({ entry, isLast }: { entry: TimelineEntry; isLast: boolean }) {
  return (
    <div className="relative flex gap-4">
      {!isLast ? <div className="absolute bottom-0 left-[15px] top-8 w-px bg-border" /> : null}
      <div
        className={`relative z-10 mt-1 h-8 w-8 shrink-0 rounded-full border ${
          entry.kind === "message"
            ? "border-[#5e6ad2]/30 bg-[#5e6ad2]/12 text-[#5e6ad2]"
            : "border-border bg-muted text-muted-foreground"
        } flex items-center justify-center`}
      >
        {entry.kind === "message" ? <MessageSquare className="h-4 w-4" /> : <Activity className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1 pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-foreground">{entry.title}</span>
          <span className="text-xs text-muted-foreground">{entry.actor}</span>
          <span className="text-xs text-muted-foreground">{entry.time}</span>
        </div>
        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-foreground/85">{entry.content}</p>
      </div>
    </div>
  );
}

function SourceInsightCard({
  label,
  accent,
  content,
}: {
  label: string;
  accent: string;
  content: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-background/80 p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${accent}`} />
        <div className="text-xs font-medium text-muted-foreground">{label}</div>
      </div>
      <p className="text-[13px] leading-7 text-foreground">
        {content}
      </p>
    </div>
  );
}

type WorkOrderExecutionStep = {
  key: string;
  stepNo: number;
  title: string;
  requiresApproval: boolean;
  completed: boolean;
  current: boolean;
  detail?: string;
  confirmable: boolean;
};

function normalizeExecutionSteps(
  detail: WorkOrderDetailPayload | null,
  actionSteps: Array<{ id: string; order: number; title: string; detail: string; hint: string }>,
): WorkOrderExecutionStep[] {
  const progress =
    detail?.step_progress_json && typeof detail.step_progress_json === "object"
      ? (detail.step_progress_json as Record<string, unknown>)
      : null;
  const completedSteps = Array.isArray(progress?.completed_steps)
    ? progress.completed_steps
        .map((item) => Number(item))
        .filter((item) => Number.isFinite(item))
    : [];
  const completedStepSet = new Set(completedSteps);
  const currentStepNo = Number(detail?.current_step_no);
  const templateSteps = Array.isArray(detail?.flow_template?.steps_json) ? detail.flow_template.steps_json : [];

  if (templateSteps.length > 0) {
    const normalizedSteps: WorkOrderExecutionStep[] = [];
    templateSteps.forEach((rawStep, index) => {
      if (!rawStep || typeof rawStep !== "object") return;
      const step = rawStep as Record<string, unknown>;
      const stepNo = Number(step.step_no ?? index + 1);
      if (!Number.isFinite(stepNo)) return;
      normalizedSteps.push({
        key: `template-${stepNo}`,
        stepNo,
        title: String(step.title || `工步 ${stepNo}`),
        requiresApproval: Boolean(step.requires_approval),
        completed: completedStepSet.has(stepNo),
        current: Number.isFinite(currentStepNo) ? currentStepNo === stepNo : index === 0,
        detail: typeof step.description === "string" ? step.description : undefined,
        confirmable: true,
      });
    });
    return normalizedSteps;
  }

  return actionSteps.map((step, index) => ({
    key: `suggested-${step.id}`,
    stepNo: step.order || index + 1,
    title: step.title,
    requiresApproval: false,
    completed: false,
    current: index === 0,
    detail: step.detail,
    confirmable: false,
  }));
}

function buildCaseDraft(
  detail: WorkOrderDetailPayload,
  sourceTask: WorkOrderDetailPayload["source_task"] | null | undefined,
  sourceTaskDetail: MaintenanceTaskDetail | null,
  actionSteps: Array<{ title: string; detail: string }>,
  diagnosisConclusion: string,
) {
  const taskTitle = sourceTaskDetail?.title?.trim() || sourceTask?.title?.trim() || buildTitle(detail);
  const processingSteps = actionSteps
    .map((item) => (item.detail && item.detail !== item.title ? `${item.title}：${item.detail}` : item.title))
    .filter(Boolean);

  return {
    title: `${taskTitle} 检修案例`,
    equipment_type: detail.device?.device_type || sourceTaskDetail?.equipment_type || "未分类设备",
    symptom_description:
      sourceTaskDetail?.symptom_description?.trim() ||
      sourceTask?.title?.trim() ||
      diagnosisConclusion,
    processing_steps: processingSteps,
    resolution_summary: diagnosisConclusion || null,
    equipment_model: detail.device?.model || sourceTaskDetail?.equipment_model || null,
    fault_type: sourceTaskDetail?.fault_type || null,
    work_order_id: formatWorkOrderCode(detail.id),
    asset_code: detail.device?.asset_code || null,
    report_source: "work_order",
    priority: "medium" as const,
    task_id: sourceTask?.task_id ?? null,
    knowledge_refs: sourceTaskDetail?.source_refs ?? [],
  };
}

export default function TicketDetailPage() {
  const params = useParams<{ ticketId: string }>();
  const router = useRouter();
  const numericId = useMemo(() => {
    const raw = params?.ticketId || "";
    const matched = String(raw).match(/\d+/);
    return matched ? Number(matched[0]) : NaN;
  }, [params]);

  const [detail, setDetail] = useState<WorkOrderDetailPayload | null>(null);
  const [events, setEvents] = useState<WorkOrderEventItem[]>([]);
  const [messages, setMessages] = useState<WorkOrderMessageItem[]>([]);
  const [sourceTaskDetail, setSourceTaskDetail] = useState<MaintenanceTaskDetail | null>(null);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [actionPending, setActionPending] = useState<"enter" | "complete" | null>(null);
  const [confirmingStepNo, setConfirmingStepNo] = useState<number | null>(null);
  const [creatingCase, setCreatingCase] = useState(false);
  const [createCaseOpen, setCreateCaseOpen] = useState(false);
  const [caseTitleDraft, setCaseTitleDraft] = useState("");
  const [caseSummaryDraft, setCaseSummaryDraft] = useState("");
  const [fillDialogOpen, setFillDialogOpen] = useState(false);
  const [fillSubmitting, setFillSubmitting] = useState(false);
  const [fillResolutionStatus, setFillResolutionStatus] = useState<"resolved" | "unresolved">("resolved");
  const [fillClosureCode, setFillClosureCode] = useState<"NORMAL" | "PART_REPLACED" | "ADJUSTED" | "OTHER" | "UNRESOLVED">("NORMAL");
  const [fillUnresolvedAction, setFillUnresolvedAction] = useState<"REOPEN_ESCALATION" | "RETRY_RETRIEVAL" | "CLOSE_UNRESOLVED">("RETRY_RETRIEVAL");
  const [fillUnresolvedReason, setFillUnresolvedReason] = useState<"EQUIPMENT_LIMIT" | "INFO_INSUFFICIENT" | "EXPERT_REQUIRED" | "USER_ABORT" | "OTHER">("INFO_INSUFFICIENT");
  const [fillDetailNotes, setFillDetailNotes] = useState("");
  const [fillFiles, setFillFiles] = useState<File[]>([]);

  const loadDetail = async (options?: { silent?: boolean }) => {
    const token = getMaintenanceToken();
    if (!token) {
      setError("当前未检测到检修域登录状态，无法查看工单详情。");
      setLoading(false);
      return;
    }
    if (!Number.isFinite(numericId)) {
      setError("工单编号无效。");
      setLoading(false);
      return;
    }
    if (!options?.silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const [detailPayload, eventsPayload, messagesPayload] = await Promise.all([
        fetchWorkOrderDetail(token, numericId),
        fetchWorkOrderEvents(token, numericId),
        fetchWorkOrderMessages(token, numericId),
      ]);
      setDetail(detailPayload);
      setEvents(eventsPayload.items);
      setMessages(messagesPayload.items);
      if (detailPayload.source_task?.task_id) {
        try {
          const taskDetailPayload = await fetchTaskDetail(detailPayload.source_task.task_id);
          setSourceTaskDetail(taskDetailPayload);
        } catch {
          setSourceTaskDetail(null);
        }
      } else {
        setSourceTaskDetail(null);
      }
    } catch (e) {
      setError(
        isMaintenanceAuthExpiredError(e)
          ? "登录已失效，请重新登录后继续查看工单详情。"
          : e instanceof Error
            ? e.message
            : "加载工单详情失败",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDetail();
  }, [numericId]);

  const title = useMemo(() => buildTitle(detail), [detail]);
  const summary = useMemo(() => buildSummary(detail, messages, events), [detail, messages, events]);
  const timeline = useMemo(() => buildTimeline(events, messages), [events, messages]);
  const statusMeta = getWorkOrderStatusMeta(detail?.status);
  const levelMeta = getMaintenanceLevelMeta(detail?.maintenance_level);
  const sourceTask = detail?.source_task;
  const latestAssistantSuggestion = useMemo(
    () => [...messages].reverse().find((item) => item.role === "assistant" && item.content?.trim())?.content || null,
    [messages],
  );
  const actionSteps = useMemo(
    () => buildActionCardsFromTask(sourceTaskDetail, sourceTask?.advice_card, latestAssistantSuggestion),
    [latestAssistantSuggestion, sourceTask?.advice_card, sourceTaskDetail],
  );
  const diagnosisConclusion = useMemo(
    () => buildDiagnosisConclusionFromTask(sourceTaskDetail, sourceTask?.diagnosis_report),
    [sourceTask?.diagnosis_report, sourceTaskDetail],
  );
  const executionSteps = useMemo(
    () => normalizeExecutionSteps(detail, actionSteps),
    [actionSteps, detail],
  );
  const hasFlowTemplateSteps = executionSteps.some((step) => step.confirmable);

  useEffect(() => {
    if (!createCaseOpen || !detail) return;
    const draft = buildCaseDraft(detail, sourceTask, sourceTaskDetail, actionSteps, diagnosisConclusion);
    setCaseTitleDraft(draft.title);
    setCaseSummaryDraft(draft.resolution_summary || "");
  }, [actionSteps, createCaseOpen, detail, diagnosisConclusion, sourceTask, sourceTaskDetail]);

  useEffect(() => {
    if (!fillDialogOpen) return;
    if (detail?.status !== "S8") {
      setFillDialogOpen(false);
      return;
    }
    setFillResolutionStatus("resolved");
    setFillClosureCode("NORMAL");
    setFillUnresolvedAction("RETRY_RETRIEVAL");
    setFillUnresolvedReason("INFO_INSUFFICIENT");
    setFillDetailNotes("");
    setFillFiles([]);
  }, [detail?.status, fillDialogOpen]);

  const handleSubmitComment = () => {
    const token = getMaintenanceToken();
    const content = comment.trim();
    if (!token || !Number.isFinite(numericId) || !content) return;
    setSubmitting(true);
    void (async () => {
      try {
        const created = await postWorkOrderMessage(token, numericId, { content });
        setComment("");
        setMessages((current) => [
          ...current,
          {
            id: created.id,
            role: "user",
            content,
            retrieval_snapshot_id: null,
            created_at: created.created_at,
          },
        ]);
        toast.success("处理记录已提交");
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "提交失败");
      } finally {
        setSubmitting(false);
      }
    })();
  };

  const handleAction = (kind: "enter" | "complete") => {
    const token = getMaintenanceToken();
    if (!token || !Number.isFinite(numericId)) return;
    setActionPending(kind);
    void (async () => {
      try {
        if (kind === "enter") {
          await enterWorkOrderMaintenance(token, numericId);
          toast.success("已进入检修流程");
        } else {
          await completeWorkOrderMaintenance(token, numericId);
          toast.success("已标记为完成检修");
        }
        await loadDetail({ silent: true });
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "操作失败");
      } finally {
        setActionPending(null);
      }
    })();
  };

  const handleConfirmStep = (stepNo: number) => {
    const token = getMaintenanceToken();
    if (!token || !Number.isFinite(numericId)) return;
    setConfirmingStepNo(stepNo);
    void (async () => {
      try {
        await confirmWorkOrderStep(token, numericId, { step_no: stepNo, mark_done: true });
        toast.success(`已确认工步 ${stepNo}`);
        await loadDetail({ silent: true });
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "工步确认失败");
      } finally {
        setConfirmingStepNo(null);
      }
    })();
  };

  const handleCreateCase = () => {
    if (!detail) return;
    setCreatingCase(true);
    void (async () => {
      try {
        const draft = buildCaseDraft(detail, sourceTask, sourceTaskDetail, actionSteps, diagnosisConclusion);
        const created = await createMaintenanceCase({
          ...draft,
          title: caseTitleDraft.trim() || draft.title,
          resolution_summary: caseSummaryDraft.trim() || draft.resolution_summary,
        });
        setCreateCaseOpen(false);
        toast.success("已转为检修案例");
        router.push(`/cases/CASE-${created.id}`);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "提交知识沉淀失败");
      } finally {
        setCreatingCase(false);
      }
    })();
  };

  const handleSubmitFilling = () => {
    const token = getMaintenanceToken();
    if (!token || !Number.isFinite(numericId)) return;
    if (fillFiles.length < 1) {
      toast.error("请至少上传一张现场凭证或结果附件");
      return;
    }
    if (fillResolutionStatus === "resolved" && fillClosureCode === "OTHER" && !fillDetailNotes.trim()) {
      toast.error("请选择“其他”时，请补充处理说明");
      return;
    }
    if (fillResolutionStatus === "unresolved" && fillUnresolvedReason === "OTHER" && !fillDetailNotes.trim()) {
      toast.error("未解决原因选择“其他”时，请补充具体说明");
      return;
    }

    setFillSubmitting(true);
    void (async () => {
      try {
        const uploaded = [];
        for (const file of fillFiles) {
          const item = await uploadMaintenanceAttachment(token, {
            file,
            biz_type: "filling",
            work_order_id: numericId,
          });
          uploaded.push(item);
        }

        await submitWorkOrderFilling(token, numericId, {
          resolution_status: fillResolutionStatus,
          closure_code: fillResolutionStatus === "resolved" ? fillClosureCode : "UNRESOLVED",
          attachment_ids: uploaded.map((item) => item.id),
          detail_notes: fillDetailNotes.trim() || null,
          post_unresolved_action: fillResolutionStatus === "unresolved" ? fillUnresolvedAction : null,
          unresolved_reason_code: fillResolutionStatus === "unresolved" ? fillUnresolvedReason : null,
        });

        setFillDialogOpen(false);
        toast.success("回填结果已提交");
        await loadDetail({ silent: true });
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "提交回填结果失败");
      } finally {
        setFillSubmitting(false);
      }
    })();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="app-main app-main-wide">
          <div className="app-card flex min-h-[360px] items-center justify-center">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              正在加载工单详情...
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (error || !detail) {
    const authExpired = error?.includes("登录已失效") ?? false;
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="app-main app-main-wide">
          <div className="app-card flex min-h-[360px] flex-col items-center justify-center px-6 text-center">
            <FileText className="mb-4 h-10 w-10 text-muted-foreground" />
            <h1 className="text-lg font-semibold text-foreground">{authExpired ? "登录已失效" : "无法查看工单详情"}</h1>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">{error || "当前工单不存在或无权限访问。"}</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Link href="/tickets" className="app-btn-secondary">
                返回工单列表
              </Link>
              {authExpired ? (
                <Link href="/login" className="app-btn-primary">
                  前往登录
                </Link>
              ) : null}
            </div>
          </div>
        </main>
      </div>
    );
  }

  const canEnterMaintenance = detail.status === "S1" || detail.status === "S3" || detail.status === "S5";
  const canCompleteMaintenance = detail.status === "S7";
  const canFillResult = detail.status === "S8";
  const hasAvailableAction = canEnterMaintenance || canCompleteMaintenance || canFillResult;

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="app-main app-main-wide space-y-6">
        <section className="app-page-head">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <Link href="/tickets" className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
                <ChevronLeft className="h-4 w-4" />
                返回列表
              </Link>
              <span className="font-mono text-sm text-muted-foreground">{formatWorkOrderCode(detail.id)}</span>
              <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium ${levelMeta.className}`}>
                {levelMeta.label}
              </span>
              <span className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium ${statusMeta.className}`}>
                {statusMeta.label}
              </span>
            </div>
            <button type="button" className="app-btn-secondary" onClick={() => void loadDetail()}>
              <RefreshCw className="h-4 w-4" />
              刷新
            </button>
          </div>
        </section>

        <section className="app-card p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{summary}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:w-[420px]">
              <div className="app-subpanel p-4">
                <div className="mb-1 text-xs text-muted-foreground">设备类型</div>
                <div className="text-sm font-medium text-foreground">{detail.device?.device_type || "--"}</div>
              </div>
              <div className="app-subpanel p-4">
                <div className="mb-1 text-xs text-muted-foreground">设备型号</div>
                <div className="text-sm font-medium text-foreground">{detail.device?.model || "--"}</div>
              </div>
              <div className="app-subpanel p-4">
                <div className="mb-1 text-xs text-muted-foreground">设备编号</div>
                <div className="text-sm font-medium text-foreground">{detail.device?.asset_code || "--"}</div>
              </div>
              <div className="app-subpanel p-4">
                <div className="mb-1 text-xs text-muted-foreground">最后更新</div>
                <div className="text-sm font-medium text-foreground">{formatDateTimeLocal(detail.updated_at)}</div>
              </div>
            </div>
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.8fr)_360px]">
          <section className="space-y-6">
            <div className="app-card">
              <div className="flex items-center justify-between border-b border-border px-5 py-4">
                <div className="inline-flex items-center gap-2 text-base font-medium text-foreground">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  执行记录
                </div>
                <span className="text-sm text-muted-foreground">{timeline.length} 条</span>
              </div>
              <div className="p-5">
                {timeline.length > 0 ? (
                  timeline.map((entry, index) => <TimelineCard key={entry.id} entry={entry} isLast={index === timeline.length - 1} />)
                ) : (
                  <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
                    当前工单暂无可展示的执行记录。
                  </div>
                )}
              </div>
            </div>

            <div className="app-card">
              <div className="flex items-center justify-between border-b border-border px-5 py-4">
                <div className="inline-flex items-center gap-2 text-base font-medium text-foreground">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  追加记录
                </div>
                <span className="text-sm text-muted-foreground">将写入真实工单消息</span>
              </div>
              <div className="p-5">
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="输入检修进展、交接说明或现场备注..."
                  rows={4}
                  className="app-textarea min-h-[120px]"
                />
                <div className="mt-3 flex justify-end">
                  <button type="button" className="app-btn-primary" onClick={handleSubmitComment} disabled={submitting || !comment.trim()}>
                    {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    提交记录
                  </button>
                </div>
              </div>
            </div>
          </section>

          <aside className="space-y-6">
            {sourceTask ? (
              <div className="app-card p-5">
                <div className="flex items-center gap-2 text-base font-semibold text-foreground">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  来源智能诊断
                </div>
                <div className="mt-4 space-y-4 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">诊断任务编号</span>
                    <span className="font-mono text-foreground">#{sourceTask.task_id}</span>
                  </div>
                  <SourceInsightCard
                    label="结论"
                    accent="bg-[#5e6ad2]"
                    content={diagnosisConclusion}
                  />
                  <Link
                    href={`/tasks/${sourceTask.task_id}?from=${encodeURIComponent(`/tickets/${detail.id}`)}`}
                    className="app-btn-secondary w-full justify-center"
                  >
                    跳转到诊断详情页
                  </Link>
                </div>
              </div>
            ) : null}

            <div className="app-card p-5">
              <h2 className="text-base font-semibold text-foreground">工单信息</h2>
              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">工单编号</span>
                  <span className="font-mono text-foreground">{formatWorkOrderCode(detail.id)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">创建时间</span>
                  <span className="text-foreground">{formatDateTimeLocal(detail.created_at)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">最后更新</span>
                  <span className="text-foreground">{formatDateTimeLocal(detail.updated_at)}</span>
                </div>
                {detail.flow_template?.name ? (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">流程模板</span>
                    <span className="text-foreground">{detail.flow_template.name}</span>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="app-card p-5">
              <h2 className="text-base font-semibold text-foreground">按步骤执行 / 确认</h2>
              <div className="mt-4 space-y-4">
                <div>
                  <div className="mb-2 text-xs text-muted-foreground">
                    {detail.flow_template?.name ? `流程模板：${detail.flow_template.name}` : "建议优先执行的步骤"}
                  </div>
                  {executionSteps.length > 0 ? (
                    <div className="space-y-2">
                      {executionSteps.map((step) => (
                        <div key={step.key} className="rounded-lg border border-border bg-muted/20 p-4">
                          <div className="flex items-start gap-3">
                            <span className={`mt-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold ${
                              step.completed
                                ? "bg-emerald-500/12 text-emerald-600 dark:text-emerald-400"
                                : step.current
                                  ? "bg-[#5e6ad2]/12 text-[#5e6ad2]"
                                  : "bg-muted text-muted-foreground"
                            }`}>
                              {step.stepNo}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <div className="text-sm font-medium text-foreground">{step.title}</div>
                                {step.current ? <span className="app-chip-muted">当前工步</span> : null}
                                {step.completed ? <span className="app-chip-muted">已确认</span> : null}
                                {step.requiresApproval ? <span className="app-chip-muted">需审批</span> : null}
                              </div>
                              {step.detail ? (
                                <p className="mt-1 text-sm leading-6 text-muted-foreground">{step.detail}</p>
                              ) : null}
                            </div>
                          </div>
                          <div className="mt-3 flex justify-end">
                            {detail.status === "S7" && step.confirmable && !step.completed ? (
                              <button
                                type="button"
                                className="app-btn-secondary"
                                onClick={() => handleConfirmStep(step.stepNo)}
                                disabled={confirmingStepNo != null || !step.current}
                              >
                                {confirmingStepNo === step.stepNo ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                                确认本步
                              </button>
                            ) : (
                              <div className="text-xs text-muted-foreground">
                                {step.completed
                                  ? "该工步已确认完成。"
                                  : detail.status === "S7"
                                    ? step.confirmable
                                      ? "需按顺序执行后确认。"
                                      : "当前为检索生成的建议步骤，未绑定真实流程模板，暂不支持工步确认。"
                                    : "进入检修后可逐步确认。"}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-border bg-muted/20 px-3 py-3 text-sm text-muted-foreground">
                      当前尚未生成可执行步骤。
                    </div>
                  )}
                  {detail.status === "S7" && !hasFlowTemplateSteps ? (
                    <div className="mt-3 rounded-lg border border-dashed border-border bg-muted/20 px-3 py-3 text-xs leading-6 text-muted-foreground">
                      当前显示的是检索生成的建议步骤，还没有绑定真实流程模板，所以可以参考执行，但不能逐步确认。
                    </div>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <div className="text-xs text-muted-foreground">当前可执行的工单操作</div>
                  {canEnterMaintenance ? (
                    <button
                      type="button"
                      className="app-btn-secondary w-full justify-center"
                      onClick={() => handleAction("enter")}
                      disabled={actionPending != null}
                    >
                      {actionPending === "enter" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wrench className="h-4 w-4" />}
                      进入检修
                    </button>
                  ) : null}
                  {canCompleteMaintenance ? (
                    <button
                      type="button"
                      className="app-btn-secondary w-full justify-center"
                      onClick={() => handleAction("complete")}
                      disabled={actionPending != null}
                    >
                      {actionPending === "complete" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                      完成检修
                    </button>
                  ) : null}
                  {canFillResult ? (
                    <button
                      type="button"
                      className="app-btn-secondary w-full justify-center"
                      onClick={() => setFillDialogOpen(true)}
                    >
                      <PenTool className="h-4 w-4" />
                      填写回填结果
                    </button>
                  ) : null}
                  {!hasAvailableAction ? (
                    <div className="rounded-lg border border-border bg-muted/20 px-3 py-3 text-sm text-muted-foreground">
                      {detail.status === "S8"
                        ? "当前检修已完成，请先填写处理结果和现场凭证，再继续后续流程。"
                        : `当前工单状态为“${statusMeta.label}”，暂时没有可继续推进的工单操作。`}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="app-card p-5">
              <h2 className="text-base font-semibold text-foreground">转为检修案例 / 提交知识沉淀</h2>
              <div className="mt-4 space-y-4">
                <div className="rounded-lg border border-border bg-muted/20 p-4 text-sm text-muted-foreground">
                  将本次工单的来源诊断、执行步骤与现场追加记录沉淀为检修案例，便于后续审核发布和知识复用。
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">案例标题</span>
                    <span className="text-right text-foreground">{buildCaseDraft(detail, sourceTask, sourceTaskDetail, actionSteps, diagnosisConclusion).title}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">来源工单</span>
                    <span className="font-mono text-foreground">{formatWorkOrderCode(detail.id)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">关联诊断</span>
                    <span className="text-foreground">{sourceTask ? `#${sourceTask.task_id}` : "无"}</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="app-btn-primary w-full justify-center"
                  onClick={() => setCreateCaseOpen(true)}
                  disabled={creatingCase}
                >
                  <PenTool className="h-4 w-4" />
                  转为检修案例
                </button>
              </div>
            </div>

            <div className="app-card p-5">
              <div className="text-base font-semibold text-foreground">记录概览</div>
              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">消息记录</span>
                  <span className="text-foreground">{messages.length} 条</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">事件记录</span>
                  <span className="text-foreground">{events.length} 条</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">来源</span>
                  <span className="text-foreground">
                    {sourceTask ? `AI诊断任务 #${sourceTask.task_id}` : "检修域工单"}
                  </span>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </main>

      <Dialog open={createCaseOpen} onOpenChange={setCreateCaseOpen}>
        <DialogContent className="max-w-lg border-border bg-popover text-popover-foreground">
          <DialogHeader>
            <DialogTitle>转为检修案例</DialogTitle>
            <DialogDescription>
              可在提交前微调案例标题和处理结果总结，其他信息将沿用当前工单与来源诊断内容。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-sm font-medium text-foreground">案例标题</div>
              <input
                value={caseTitleDraft}
                onChange={(e) => setCaseTitleDraft(e.target.value)}
                className="app-input w-full"
                placeholder="请输入案例标题"
              />
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-foreground">处理结果总结</div>
              <textarea
                value={caseSummaryDraft}
                onChange={(e) => setCaseSummaryDraft(e.target.value)}
                rows={4}
                className="app-textarea min-h-[120px]"
                placeholder="补充本次检修结果总结"
              />
            </div>
          </div>
          <DialogFooter>
            <button type="button" className="app-btn-secondary" onClick={() => setCreateCaseOpen(false)} disabled={creatingCase}>
              取消
            </button>
            <button type="button" className="app-btn-primary" onClick={handleCreateCase} disabled={creatingCase || !caseTitleDraft.trim()}>
              {creatingCase ? <Loader2 className="h-4 w-4 animate-spin" /> : <PenTool className="h-4 w-4" />}
              提交知识沉淀
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={fillDialogOpen}
        onOpenChange={(open) => {
          if (fillSubmitting) return;
          setFillDialogOpen(open);
        }}
      >
        <DialogContent className="max-w-lg border-border bg-popover text-popover-foreground">
          <DialogHeader>
            <DialogTitle>填写回填结果</DialogTitle>
            <DialogDescription>
              检修完成后，补充本次处理结果、原因说明和现场凭证，提交后工单将进入待验收。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <div className="text-sm font-medium text-foreground">处理结果</div>
              <select
                value={fillResolutionStatus}
                onChange={(e) => {
                  const nextValue = e.target.value as "resolved" | "unresolved";
                  setFillResolutionStatus(nextValue);
                  setFillClosureCode(nextValue === "resolved" ? "NORMAL" : "UNRESOLVED");
                }}
                className="app-select h-10 w-full"
              >
                <option value="resolved">已解决</option>
                <option value="unresolved">未解决</option>
              </select>
            </div>

            {fillResolutionStatus === "resolved" ? (
              <div className="grid gap-2">
                <div className="text-sm font-medium text-foreground">处理方式</div>
                <select
                  value={fillClosureCode}
                  onChange={(e) => setFillClosureCode(e.target.value as "NORMAL" | "PART_REPLACED" | "ADJUSTED" | "OTHER")}
                  className="app-select h-10 w-full"
                >
                  <option value="NORMAL">正常处理恢复</option>
                  <option value="PART_REPLACED">已更换部件</option>
                  <option value="ADJUSTED">已调整参数</option>
                  <option value="OTHER">其他情况</option>
                </select>
              </div>
            ) : (
              <>
                <div className="grid gap-2">
                  <div className="text-sm font-medium text-foreground">未解决原因</div>
                  <select
                    value={fillUnresolvedReason}
                    onChange={(e) =>
                      setFillUnresolvedReason(
                        e.target.value as "EQUIPMENT_LIMIT" | "INFO_INSUFFICIENT" | "EXPERT_REQUIRED" | "USER_ABORT" | "OTHER",
                      )
                    }
                    className="app-select h-10 w-full"
                  >
                    <option value="INFO_INSUFFICIENT">信息不足，暂无法判断</option>
                    <option value="EXPERT_REQUIRED">需要专家进一步介入</option>
                    <option value="EQUIPMENT_LIMIT">受设备条件限制</option>
                    <option value="USER_ABORT">现场中止处理</option>
                    <option value="OTHER">其他原因</option>
                  </select>
                </div>
                <div className="grid gap-2">
                  <div className="text-sm font-medium text-foreground">后续动作</div>
                  <select
                    value={fillUnresolvedAction}
                    onChange={(e) =>
                      setFillUnresolvedAction(
                        e.target.value as "REOPEN_ESCALATION" | "RETRY_RETRIEVAL" | "CLOSE_UNRESOLVED",
                      )
                    }
                    className="app-select h-10 w-full"
                  >
                    <option value="RETRY_RETRIEVAL">重新检索方案</option>
                    <option value="REOPEN_ESCALATION">发起升级会诊</option>
                    <option value="CLOSE_UNRESOLVED">保留未解决并关闭</option>
                  </select>
                </div>
              </>
            )}

            <div className="grid gap-2">
              <div className="text-sm font-medium text-foreground">补充说明</div>
              <textarea
                value={fillDetailNotes}
                onChange={(e) => setFillDetailNotes(e.target.value)}
                rows={4}
                className="app-textarea min-h-[120px]"
                placeholder={
                  fillResolutionStatus === "resolved"
                    ? "填写处理过程、替换部件、复测结果等"
                    : "说明当前未解决的原因、现场限制和建议后续动作"
                }
              />
            </div>

            <div className="grid gap-2">
              <div className="text-sm font-medium text-foreground">现场凭证 <span className="text-red-400">*</span></div>
              <input
                type="file"
                multiple
                className="app-input h-auto w-full cursor-pointer py-2"
                onChange={(e) => setFillFiles(Array.from(e.target.files || []))}
                accept=".jpg,.jpeg,.png,.webp,.pdf"
              />
              <div className="text-xs text-muted-foreground">
                至少上传 1 个附件，支持图片或 PDF，单文件不超过 10MB。
              </div>
              {fillFiles.length > 0 ? (
                <div className="rounded-lg border border-border bg-muted/20 px-3 py-3 text-xs text-muted-foreground">
                  已选择：{fillFiles.map((file) => file.name).join("、")}
                </div>
              ) : null}
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <button
              type="button"
              className="app-btn-secondary"
              onClick={() => setFillDialogOpen(false)}
              disabled={fillSubmitting}
            >
              取消
            </button>
            <button
              type="button"
              className="app-btn-primary"
              onClick={handleSubmitFilling}
              disabled={fillSubmitting || fillFiles.length < 1}
            >
              {fillSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <PenTool className="h-4 w-4" />}
              提交回填结果
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

