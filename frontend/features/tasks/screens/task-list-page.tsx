"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  fetchMaintenanceHistory,
  createMaintenanceTask,
  deleteMaintenanceTask,
  fetchHealth,
  postAgentAssist,
  type MaintenanceTaskHistoryItem,
  type MaintenanceTaskDetail,
} from "@/features/tasks/api";
import {
  Search,
  Filter,
  Plus,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  MoreHorizontal,
  ExternalLink,
  Trash2,
  ListFilter,
  Calendar,
  Cpu,
  FileText,
  ImagePlus,
  FileUp,
  X,
} from "lucide-react";
import { Header } from "@/shared/components/brand/app-header";
import { formatDateTimeLocal, formatDurationBetween } from "@/shared/lib/utils";
import { generateMockAssetCode } from "@/features/tasks/lib/mock-asset-code";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/lib/utils";
import { DEMO_MODE_CHANGED_EVENT } from "@/shared/lib/demo-mode";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Label } from "@/shared/components/ui/label";
import { Input } from "@/shared/components/ui/input";
import { Textarea } from "@/shared/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

// 状态类型
type TaskStatus = "running" | "completed" | "failed" | "pending";
type PageState = "normal" | "loading" | "empty" | "error";

type MaintenanceLevelOption = "routine" | "standard" | "emergency";
type DiagnosePhase = "idle" | "running" | "result";

// 任务数据类型
interface Task {
  id: string;
  timeRange: string;
  symptom: string;
  progress: string;
  status: TaskStatus;
  duration: string;
  createdAt: string;
  maintenanceLevel: MaintenanceLevelOption;
}

function deriveTaskDuration(h: MaintenanceTaskHistoryItem) {
  if (h.run_started_at && h.run_finished_at) {
    return formatDurationBetween(h.run_started_at, h.run_finished_at) || "--";
  }
  if (h.run_started_at && String(h.status || "").toLowerCase() === "in_progress") {
    return formatDurationBetween(h.run_started_at, new Date().toISOString()) || "进行中";
  }
  return formatDurationBetween(h.created_at, h.updated_at) || "--";
}

function mapHistoryToTask(h: MaintenanceTaskHistoryItem): Task {
  const st = (h.status || "").toLowerCase();
  let status: TaskStatus = "pending";
  if (st === "in_progress") status = "running";
  else if (st === "completed") status = "completed";
  else if (st === "skipped") status = "failed";
  if (h.total_steps > 0 && h.completed_steps >= h.total_steps) {
    status = "completed";
  }
  const rawLevel = String(h.maintenance_level || "standard").toLowerCase();
  const maintenanceLevel: MaintenanceLevelOption =
    rawLevel === "routine" || rawLevel === "emergency" ? rawLevel : "standard";
  const c = formatDateTimeLocal(h.created_at);
  const u = formatDateTimeLocal(h.updated_at);
  const timeRange = u !== c && u !== "--" ? `${c} → ${u}` : c;
  return {
    id: String(h.id),
    timeRange,
    symptom: h.title || h.equipment_type,
    progress: `${h.completed_steps}/${h.total_steps} 步`,
    status,
    duration: deriveTaskDuration(h),
    createdAt: c,
    maintenanceLevel,
  };
}

function MaintenanceLevelTag({ level }: { level: MaintenanceLevelOption }) {
  const meta = {
    emergency: {
      label: "紧急",
      className: "border-red-500/30 bg-red-500/10 text-red-500 dark:text-red-400",
    },
    standard: {
      label: "标准",
      className: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
    },
    routine: {
      label: "例行",
      className: "border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-400",
    },
  } as const;

  const current = meta[level];
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium ${current.className}`}>
      {current.label}
    </span>
  );
}

// 状态标签组件
function StatusTag({ status }: { status: TaskStatus }) {
  const config = {
    running: {
      bg: "bg-blue-500/10",
      border: "border-blue-500/30",
      text: "text-blue-400",
      label: "进行中",
      icon: Loader2,
      animate: true,
    },
    completed: {
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/30",
      text: "text-emerald-400",
      label: "已完成",
      icon: CheckCircle2,
      animate: false,
    },
    failed: {
      bg: "bg-red-500/10",
      border: "border-red-500/30",
      text: "text-red-400",
      label: "失败",
      icon: XCircle,
      animate: false,
    },
    pending: {
      bg: "bg-amber-500/10",
      border: "border-amber-500/30",
      text: "text-amber-400",
      label: "等待中",
      icon: Clock,
      animate: false,
    },
  };

  const { bg, border, text, label, icon: Icon, animate } = config[status];

  return (
    <span
      className={`app-badge ${bg} ${border} ${text}`}
    >
      <Icon className={`w-3 h-3 ${animate ? "animate-spin" : ""}`} />
      {label}
    </span>
  );
}

// 统计卡片组件
function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="app-kpi-card flex items-center gap-3 px-4 py-3">
      <div
        className={`flex items-center justify-center w-9 h-9 rounded-lg ${color}`}
      >
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <div className="text-xl font-semibold text-foreground">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

// 骨架行组件
function SkeletonRow() {
  return (
    <tr className="border-b border-border">
      {[...Array(7)].map((_, i) => (
        <td key={i} className="px-4 py-4">
          <div
            className={`app-skeleton h-4 ${
              i === 2 ? "w-32" : i === 6 ? "w-16" : "w-20"
            }`}
          />
        </td>
      ))}
    </tr>
  );
}

// 空状态组件
function EmptyState({ onCreate }: { onCreate?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="app-empty-icon mb-4 h-16 w-16 rounded-full">
        <FileText className="w-7 h-7" />
      </div>
      <h3 className="mb-2 text-lg font-medium text-foreground">
        暂无诊断任务
      </h3>
      <p className="mb-6 max-w-sm text-center text-sm text-muted-foreground">
        创建首个诊断任务，开始分析传感器数据并生成诊断报告
      </p>
      <button
        type="button"
        onClick={onCreate}
        className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#5e6ad2] hover:bg-[#7170ff] text-white text-sm font-medium rounded-md transition-colors"
      >
        <Plus className="w-4 h-4" />
        创建首个诊断任务
      </button>
    </div>
  );
}

// 错误状态组件
function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg">
      <div className="flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-red-400" />
        <div>
          <p className="text-sm font-medium text-red-400">数据加载失败</p>
          <p className="text-xs text-red-400/70">
            无法获取任务列表，请检查网络连接后重试
          </p>
        </div>
      </div>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 text-sm font-medium rounded-md transition-colors"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        重试
      </button>
    </div>
  );
}

// 任务行操作菜单
function TaskRowActions({
  taskId,
  onDelete,
}: {
  taskId: string;
  onDelete: (taskId: string) => Promise<void>;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="任务操作"
        >
          <MoreHorizontal className="w-4 h-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={8}
        className="w-40 border-border bg-popover"
      >
        <DropdownMenuItem
          className="text-foreground focus:bg-accent focus:text-accent-foreground"
          asChild
        >
          <Link href={`/tasks/${taskId}`} className="flex items-center gap-2">
            <ExternalLink className="w-3.5 h-3.5" />
            查看详情
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="text-red-400 focus:bg-red-500/10 focus:text-red-300"
          onSelect={() => {
            void onDelete(taskId);
          }}
        >
          <Trash2 className="w-3.5 h-3.5" />
          删除任务
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// 分页组件
function Pagination({
  currentPage,
  totalPages,
  totalCount,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  totalCount: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="flex items-center justify-between border-t border-border px-4 py-3">
      <div className="text-sm text-muted-foreground">
        共 {totalCount} 条记录，第 {currentPage} / {totalPages} 页
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        {[...Array(Math.min(totalPages, 5))].map((_, i) => {
          const page = i + 1;
          return (
            <button
              key={page}
              onClick={() => onPageChange(page)}
              className={`w-8 h-8 rounded-md text-sm font-medium transition-colors ${
                currentPage === page
                  ? "bg-[#5e6ad2] text-white"
                  : "border border-border text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {page}
            </button>
          );
        })}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// 筛选器下拉组件（应用时请求 /api/v1/history）
function FilterDropdown({
  onApply,
}: {
  onApply: (apiStatus: string | undefined) => void;
}) {
  const [open, setOpen] = useState(false);
  const [statusSel, setStatusSel] = useState("");

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
      >
        <ListFilter className="w-4 h-4" />
        <span className="hidden sm:inline">筛选</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-10 z-20 w-56 p-3 app-overlay-panel">
            <div className="mb-3">
              <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
                任务状态
              </label>
              <select
                value={statusSel}
                onChange={(e) => setStatusSel(e.target.value)}
                className="app-select w-full py-2"
              >
                <option value="">全部状态</option>
                <option value="in_progress">进行中</option>
                <option value="completed">已完成</option>
                <option value="skipped">已跳过</option>
                <option value="pending">等待中</option>
              </select>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setStatusSel("");
                  onApply(undefined);
                  setOpen(false);
                }}
                className="flex-1 rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-muted"
              >
                重置
              </button>
              <button
                type="button"
                onClick={() => {
                  onApply(statusSel || undefined);
                  setOpen(false);
                }}
                className="app-btn-primary flex-1 px-3 py-1.5"
              >
                应用
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// 主页面组件
export default function TasksPage() {
  const router = useRouter();
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const logInputRef = useRef<HTMLInputElement | null>(null);
  const [pageState, setPageState] = useState<PageState>("normal");
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [listTasks, setListTasks] = useState<Task[]>([]);

  const [diagSymptom, setDiagSymptom] = useState("");
  const [diagEquipmentType, setDiagEquipmentType] = useState("");
  const [diagAssetCode, setDiagAssetCode] = useState("");
  const [diagLevel, setDiagLevel] = useState<MaintenanceLevelOption>("standard");
  const [diagSubmitting, setDiagSubmitting] = useState(false);
  const [diagError, setDiagError] = useState<string | null>(null);
  const [diagImageFile, setDiagImageFile] = useState<File | null>(null);
  const [diagLogFile, setDiagLogFile] = useState<File | null>(null);
  const [latestTaskId, setLatestTaskId] = useState<number | null>(null);
  const [latestAdvice, setLatestAdvice] = useState<string | null>(null);
  const [latestSourceRefs, setLatestSourceRefs] = useState<MaintenanceTaskDetail["source_refs"]>([]);
  const [diagPhase, setDiagPhase] = useState<DiagnosePhase>("idle");
  const [diagStepIndex, setDiagStepIndex] = useState(0);

  const [createTaskOpen, setCreateTaskOpen] = useState(false);
  const [createTaskSubmitting, setCreateTaskSubmitting] = useState(false);
  const [createTaskError, setCreateTaskError] = useState<string | null>(null);
  const [equipmentType, setEquipmentType] = useState("");
  const [equipmentModel, setEquipmentModel] = useState("");
  const [assetCode, setAssetCode] = useState("");
  const [maintenanceLevel, setMaintenanceLevel] =
    useState<MaintenanceLevelOption>("standard");
  const [symptomDescription, setSymptomDescription] = useState("");

  /** 与筛选器同步，供列表刷新与轮询复用 */
  const [apiStatusFilter, setApiStatusFilter] = useState<string | undefined>(
    undefined,
  );

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    try {
      const r = await fetchMaintenanceHistory({
        limit: 50,
        status: apiStatusFilter,
      });
      setListTasks(r.tasks.map(mapHistoryToTask));
      setPageState(r.tasks.length ? "normal" : "empty");
    } catch {
      setPageState("error");
    }
  }, [apiStatusFilter]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    const handleModeChanged = () => {
      void loadTasks();
    };
    window.addEventListener(DEMO_MODE_CHANGED_EVENT, handleModeChanged as EventListener);
    return () => {
      window.removeEventListener(DEMO_MODE_CHANGED_EVENT, handleModeChanged as EventListener);
    };
  }, [loadTasks]);

  useEffect(() => {
    if (!createTaskOpen) return;
    setCreateTaskError(null);
    setEquipmentType("");
    setEquipmentModel("");
    setAssetCode("");
    setMaintenanceLevel("standard");
    setSymptomDescription("");
  }, [createTaskOpen]);

  const readFileAsText = useCallback((file: File) => {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
      reader.onerror = () => reject(new Error(`读取文件「${file.name}」失败`));
      reader.readAsText(file, "utf-8");
    });
  }, []);

  const readFileAsDataUrl = useCallback((file: File) => {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
      reader.onerror = () => reject(new Error(`读取文件「${file.name}」失败`));
      reader.readAsDataURL(file);
    });
  }, []);

  const handleDiagImagePick = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setDiagError("请选择有效图片文件");
      event.target.value = "";
      return;
    }
    setDiagImageFile(file);
    setDiagError(null);
  };

  const handleDiagLogPick = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (!file) return;
    setDiagLogFile(file);
    setDiagError(null);
  };

  const submitCreateTask = () => {
    const et = equipmentType.trim();
    const sym = symptomDescription.trim();
    if (!et) {
      setCreateTaskError("请填写设备类型");
      return;
    }
    if (!sym) {
      setCreateTaskError("请填写故障现象或观察说明（创建任务必填）");
      return;
    }
    setCreateTaskError(null);
    void (async () => {
      setCreateTaskSubmitting(true);
      try {
        await createMaintenanceTask({
          equipment_type: et,
          equipment_model: equipmentModel.trim() || undefined,
          asset_code: assetCode.trim() || undefined,
          maintenance_level: maintenanceLevel,
          symptom_description: sym,
          source_chunk_ids: [],
        });
        setCreateTaskOpen(false);
        await loadTasks();
        setPageState("normal");
      } catch (e) {
        setCreateTaskError(
          e instanceof Error ? e.message : "创建失败，请稍后重试",
        );
      } finally {
        setCreateTaskSubmitting(false);
      }
    })();
  };

  const runSmartDiagnose = useCallback(() => {
    const sym = diagSymptom.trim()
    const et = diagEquipmentType.trim()
    const normalizedAssetCode = diagAssetCode.trim() || generateMockAssetCode()
    if (!sym) {
      setDiagError("请填写故障现象或观察说明")
      return
    }
    if (!et) {
      setDiagError("请填写设备类型")
      return
    }
    setDiagError(null)
    if (!diagAssetCode.trim()) {
      setDiagAssetCode(normalizedAssetCode)
    }
    void (async () => {
      setDiagSubmitting(true)
      setDiagPhase("running")
      setDiagStepIndex(0)
      const phaseTimer = window.setInterval(() => {
        setDiagStepIndex((prev) => (prev < 4 ? prev + 1 : prev))
      }, 700)
      try {
        let composedSymptom = sym;
        if (diagLogFile) {
          const rawLog = await readFileAsText(diagLogFile);
          const compactLog = rawLog.replace(/\r/g, "").trim();
          if (compactLog) {
            composedSymptom = `${sym}\n\n[现场日志：${diagLogFile.name}]\n${compactLog.slice(0, 4000)}`;
          }
        }

        let sourceChunkIds: number[] = [];
        if (diagImageFile || diagLogFile) {
          let imageBase64: string | undefined;
          let imageMimeType: string | undefined;
          let imageFilename: string | undefined;
          if (diagImageFile) {
            const dataUrl = await readFileAsDataUrl(diagImageFile);
            imageBase64 = dataUrl.includes(",") ? dataUrl.split(",")[1] : dataUrl;
            imageMimeType = diagImageFile.type || "image/png";
            imageFilename = diagImageFile.name;
          }
          const assistResult = await postAgentAssist({
            query: composedSymptom,
            equipment_type: et,
            asset_code: normalizedAssetCode,
            maintenance_level: diagLevel,
            limit: 5,
            selected_chunk_ids: [],
            image_base64: imageBase64,
            image_mime_type: imageMimeType,
            image_filename: imageFilename,
          });
          if (assistResult.effective_query?.trim()) {
            composedSymptom = assistResult.effective_query.trim();
          }
          sourceChunkIds = (assistResult.knowledge_results ?? [])
            .map((item) => Number(item.chunk_id))
            .filter((item) => Number.isFinite(item) && item > 0);
        }

        const created = await createMaintenanceTask({
          equipment_type: et,
          asset_code: normalizedAssetCode,
          maintenance_level: diagLevel,
          symptom_description: composedSymptom,
          source_chunk_ids: sourceChunkIds,
        })
        await loadTasks()
        router.push(`/tasks/${created.id}?action=process`)
        return
      } catch (e) {
        setDiagError(e instanceof Error ? e.message : "诊断失败，请稍后重试")
        setDiagPhase("idle")
      } finally {
        window.clearInterval(phaseTimer)
        setDiagSubmitting(false)
      }
    })()
  }, [diagAssetCode, diagEquipmentType, diagImageFile, diagLevel, diagLogFile, diagSymptom, loadTasks, readFileAsDataUrl, readFileAsText, router])

  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      const id = Number(taskId);
      if (!Number.isFinite(id)) return;
      setDeleteTargetId(taskId);
      setDeleteError(null);
      setDeleteDialogOpen(true);
    },
    [loadTasks],
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTargetId) return;
    const id = Number(deleteTargetId);
    if (!Number.isFinite(id)) return;
    setDeleteSubmitting(true);
    setDeleteError(null);
    try {
      await deleteMaintenanceTask(id);
      setDeleteDialogOpen(false);
      setDeleteTargetId(null);
      await loadTasks();
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "删除任务失败，请稍后重试");
    } finally {
      setDeleteSubmitting(false);
    }
  }, [deleteTargetId, loadTasks]);

  /** 存在待处理或进行中任务时定时拉取，便于状态同步到最新结果 */
  const hasActiveInList = useMemo(
    () => listTasks.some((t) => t.status === "running" || t.status === "pending"),
    [listTasks],
  );

  useEffect(() => {
    if (!hasActiveInList || pageState === "error") return;
    const tick = () => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") {
        return;
      }
      void loadTasks();
    };
    const id = window.setInterval(tick, 4000);
    return () => window.clearInterval(id);
  }, [hasActiveInList, loadTasks, pageState]);

  const displayTasks = useMemo(() => {
    const base = listTasks;
    return base.filter((task) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        task.id.toLowerCase().includes(q) ||
        task.symptom.toLowerCase().includes(q)
      );
    });
  }, [listTasks, searchQuery]);

  const stats = useMemo(() => {
    const src = listTasks;
    return {
      today: src.length,
      running: src.filter((t) => t.status === "running").length,
      completed: src.filter((t) => t.status === "completed").length,
      failed: src.filter((t) => t.status === "failed").length,
    };
  }, [listTasks]);

  const totalPages = Math.max(1, Math.ceil(displayTasks.length / 10) || 1);
  const pagedTasks = useMemo(() => {
    const start = (currentPage - 1) * 10;
    return displayTasks.slice(start, start + 10);
  }, [displayTasks, currentPage]);
  const diagnoseSteps = [
    "正在解析故障描述",
    "正在召回相关知识",
    "正在重排序证据",
    "正在生成诊断建议",
    "正在校验输出完整性",
  ] as const;

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="app-main">
        {/* 智能诊断输入区 */}
        <section className="app-card p-5 mb-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold text-foreground">智能检修助手</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                输入故障现象、选择设备或上传材料，系统将检索相关知识并生成诊断建议。
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleDiagImagePick}
              />
              <input
                ref={logInputRef}
                type="file"
                accept=".log,.txt,.json,.csv,text/plain,application/json,text/csv"
                className="hidden"
                onChange={handleDiagLogPick}
              />
              <Button
                type="button"
                variant="outline"
                className="h-9"
                onClick={() => imageInputRef.current?.click()}
              >
                <ImagePlus className="h-4 w-4" />
                上传图片
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-9"
                onClick={() => logInputRef.current?.click()}
              >
                <FileUp className="h-4 w-4" />
                上传日志
              </Button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-12">
            <div className="lg:col-span-7">
                <Textarea
                  value={diagSymptom}
                  onChange={(e) => setDiagSymptom(e.target.value)}
                  rows={3}
                  placeholder="请输入故障描述，如：压缩机 ERR-102 报错，伴随异常振动"
                  className="min-h-[88px]"
                />
              </div>
            <div className="lg:col-span-3 space-y-3">
              <Input
                value={diagEquipmentType}
                onChange={(e) => setDiagEquipmentType(e.target.value)}
                placeholder="设备类型（如：压缩机）"
              />
                <Input
                  value={diagAssetCode}
                  onChange={(e) => setDiagAssetCode(e.target.value)}
                  placeholder="设备编号（如：CMP-102，留空将自动生成）"
                />
            </div>
            <div className="lg:col-span-2 space-y-3">
              <Select
                value={diagLevel}
                onValueChange={(v) => setDiagLevel(v as MaintenanceLevelOption)}
              >
                <SelectTrigger className="h-10">
                  <SelectValue placeholder="检修等级" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="routine">例行</SelectItem>
                  <SelectItem value="standard">标准</SelectItem>
                  <SelectItem value="emergency">紧急</SelectItem>
                </SelectContent>
              </Select>
              <Button
                type="button"
                className="h-10 w-full"
                onClick={runSmartDiagnose}
                disabled={diagSubmitting}
              >
                {diagSubmitting ? "诊断中…" : "开始检修"}
              </Button>
            </div>
          </div>

          {diagImageFile || diagLogFile ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {diagImageFile ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs text-foreground">
                  <ImagePlus className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="max-w-[220px] truncate">{diagImageFile.name}</span>
                  <button
                    type="button"
                    className="text-muted-foreground transition-colors hover:text-foreground"
                    onClick={() => {
                      setDiagImageFile(null);
                      if (imageInputRef.current) imageInputRef.current.value = "";
                    }}
                    aria-label="移除图片"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : null}
              {diagLogFile ? (
                <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs text-foreground">
                  <FileUp className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="max-w-[220px] truncate">{diagLogFile.name}</span>
                  <button
                    type="button"
                    className="text-muted-foreground transition-colors hover:text-foreground"
                    onClick={() => {
                      setDiagLogFile(null);
                      if (logInputRef.current) logInputRef.current.value = "";
                    }}
                    aria-label="移除日志"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          {diagError ? (
            <p className="mt-3 text-sm text-red-400" role="alert">
              {diagError}
            </p>
          ) : null}

          {/* 输入 → 诊断中 → 结果 三态 */}
          <div className="mt-5 grid gap-4 lg:grid-cols-12">
            {diagPhase === "running" ? (
              <div className="lg:col-span-12 app-subpanel p-4">
                <div className="text-sm font-medium text-foreground">诊断中</div>
                <div className="mt-3 space-y-2">
                  {diagnoseSteps.map((step, idx) => (
                    <div key={step} className="flex items-center gap-2 text-sm">
                      <span
                        className={cn(
                          "inline-flex h-2.5 w-2.5 rounded-full",
                          idx < diagStepIndex ? "bg-emerald-400" : idx === diagStepIndex ? "bg-blue-400 animate-pulse" : "bg-zinc-500",
                        )}
                      />
                      <span className={idx <= diagStepIndex ? "text-foreground" : "text-muted-foreground"}>{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : diagPhase === "result" ? (
              <>
                <div className="lg:col-span-8 app-subpanel p-4">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium text-foreground">诊断结果</div>
                    {latestTaskId ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-8"
                        onClick={() => (window.location.href = `/tasks/${latestTaskId}`)}
                      >
                        查看任务详情
                      </Button>
                    ) : null}
                  </div>
                  <div className="mt-3 space-y-3 text-sm text-muted-foreground">
                    {latestAdvice ? (
                      <div className="rounded-lg border border-border bg-background p-3 text-xs leading-6 text-muted-foreground">
                        <div className="mb-1 font-medium text-foreground">智能建议</div>
                        {latestAdvice}
                      </div>
                    ) : (
                      <p>诊断任务已创建，请进入任务详情页查看完整诊断流程。</p>
                    )}
                  </div>
                </div>
                <div className="lg:col-span-4 app-subpanel p-4">
                  <div className="text-sm font-medium text-foreground">引用知识</div>
                  {latestSourceRefs && latestSourceRefs.length > 0 ? (
                    <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                      {latestSourceRefs.map((ref) => (
                        <li key={ref.chunk_id}>
                          [{ref.source_name}] 《{ref.title}》
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-muted-foreground">暂无引用知识</p>
                  )}
                </div>
              </>
            ) : (
              <div className="lg:col-span-12 app-subpanel p-4 text-sm text-muted-foreground">
                点击「开始检修」后，将直接跳转到诊断详情页，并进入检索与推理流程。
              </div>
            )}
          </div>
        </section>

        {/* 操作栏 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-lg font-semibold text-foreground">诊断任务记录</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              历史任务用于复盘与沉淀知识，可从详情页生成工单/归档案例
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative flex-1 sm:flex-none">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="搜索任务ID或症状..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="app-input w-full py-2 pl-9 pr-4 sm:w-64"
              />
            </div>
            <FilterDropdown
              onApply={(st) => {
                setApiStatusFilter(st);
              }}
            />
            <button
              type="button"
              className="app-btn-primary whitespace-nowrap"
              onClick={() => setCreateTaskOpen(true)}
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">新建诊断任务</span>
            </button>
          </div>
        </div>

        {/* 统计指标条 */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <StatCard
            label="今日任务"
            value={stats.today}
            icon={Calendar}
            color="bg-[#5e6ad2]/20 text-[#7170ff]"
          />
          <StatCard
            label="进行中"
            value={stats.running}
            icon={Loader2}
            color="bg-blue-500/20 text-blue-400"
          />
          <StatCard
            label="已完成"
            value={stats.completed}
            icon={CheckCircle2}
            color="bg-emerald-500/20 text-emerald-400"
          />
          <StatCard
            label="失败"
            value={stats.failed}
            icon={XCircle}
            color="bg-red-500/20 text-red-400"
          />
        </div>

        {/* 错误状态 */}
        {pageState === "error" && (
          <div className="mb-6">
            <ErrorState
              onRetry={() => {
                void loadTasks();
                setPageState("normal");
              }}
            />
          </div>
        )}

        {/* 任务表格 */}
        <div className="app-card overflow-visible">
          {pageState === "empty" ? (
            <EmptyState onCreate={() => setCreateTaskOpen(true)} />
          ) : (
            <>
              {/* 桌面端表格 */}
              <div className="hidden lg:block overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="app-table-head border-b border-border">
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        任务ID
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        创建 / 更新
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        症状描述
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        任务进度
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        状态
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        紧急程度
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
                        耗时
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider">
                        操作
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageState === "loading" ? (
                      [...Array(5)].map((_, i) => <SkeletonRow key={i} />)
                    ) : (
                      pagedTasks.map((task) => (
                        <tr
                          key={task.id}
                          className="app-table-row cursor-pointer group"
                          onClick={() =>
                            (window.location.href = `/tasks/${task.id}`)
                          }
                        >
                          <td className="px-4 py-4">
                            <span className="text-sm font-mono text-[#7170ff]">
                              {task.id}
                            </span>
                          </td>
                          <td className="px-4 py-4">
                            <span className="text-sm text-foreground">
                              {task.timeRange}
                            </span>
                          </td>
                          <td className="px-4 py-4">
                            <span className="text-sm text-foreground">
                              {task.symptom}
                            </span>
                          </td>
                          <td className="px-4 py-4">
                            <span className="app-chip-muted gap-1.5 rounded px-2 py-0.5">
                              <Cpu className="w-3 h-3" />
                              {task.progress}
                            </span>
                          </td>
                          <td className="px-4 py-4">
                            <StatusTag status={task.status} />
                          </td>
                          <td className="px-4 py-4">
                            <MaintenanceLevelTag level={task.maintenanceLevel} />
                          </td>
                          <td className="px-4 py-4">
                            <span className="text-sm text-muted-foreground">
                              {task.duration}
                            </span>
                          </td>
                          <td
                            className="px-4 py-4 text-right"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <TaskRowActions taskId={task.id} onDelete={handleDeleteTask} />
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* 移动端卡片列表 */}
              <div className="divide-y divide-border lg:hidden">
                {pageState === "loading"
                  ? [...Array(3)].map((_, i) => (
                      <div key={i} className="p-4 space-y-3">
                        <div className="flex justify-between">
                          <div className="app-skeleton h-4 w-28" />
                          <div className="app-skeleton h-6 w-16 rounded-full" />
                        </div>
                        <div className="app-skeleton h-4 w-full" />
                        <div className="flex justify-between">
                          <div className="app-skeleton h-3 w-24" />
                          <div className="app-skeleton h-3 w-16" />
                        </div>
                      </div>
                    ))
                  : pagedTasks.map((task) => (
                      <Link
                        key={task.id}
                        href={`/tasks/${task.id}`}
                        className="block p-4 transition-colors hover:bg-muted/45"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-mono text-[#7170ff]">
                              {task.id}
                            </span>
                            <MaintenanceLevelTag level={task.maintenanceLevel} />
                          </div>
                          <StatusTag status={task.status} />
                        </div>
                        <p className="mb-2 text-sm text-foreground">
                          {task.symptom}
                        </p>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {task.timeRange}
                          </span>
                          <span className="flex items-center gap-1">
                            <Cpu className="w-3 h-3" />
                            {task.progress}
                          </span>
                        </div>
                      </Link>
                    ))}
              </div>

              {/* 分页 */}
              {pageState !== "loading" && (
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  totalCount={displayTasks.length}
                  onPageChange={setCurrentPage}
                />
              )}
            </>
          )}
        </div>
      </main>

      <Dialog open={createTaskOpen} onOpenChange={setCreateTaskOpen}>
        <DialogContent
          showCloseButton
          className="max-w-md border-border bg-popover text-popover-foreground sm:max-w-md"
        >
          <DialogHeader>
            <DialogTitle>创建诊断任务</DialogTitle>
            <DialogDescription>
              填写设备与现象后提交，系统将创建检修任务并刷新列表。
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              submitCreateTask();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="tasks-eq-type" className="text-foreground">
                设备类型 <span className="text-red-400">*</span>
              </Label>
              <Input
                id="tasks-eq-type"
                name="equipment_type"
                placeholder="例如：离心泵、数控机床主轴"
                value={equipmentType}
                onChange={(e) => setEquipmentType(e.target.value)}
                className="app-input"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tasks-eq-model" className="text-foreground">
                设备型号
              </Label>
              <Input
                id="tasks-eq-model"
                name="equipment_model"
                placeholder="选填，如 DM-1000"
                value={equipmentModel}
                onChange={(e) => setEquipmentModel(e.target.value)}
                className="app-input"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tasks-asset-code" className="text-foreground">
                设备编号
              </Label>
              <Input
                id="tasks-asset-code"
                name="asset_code"
                placeholder="选填，资产编码或现场编号"
                value={assetCode}
                onChange={(e) => setAssetCode(e.target.value)}
                className="app-input"
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tasks-maint-level" className="text-foreground">
                检修等级
              </Label>
              <Select
                value={maintenanceLevel}
                onValueChange={(v) =>
                  setMaintenanceLevel(v as MaintenanceLevelOption)
                }
              >
                <SelectTrigger
                  id="tasks-maint-level"
                  className="h-9 w-full border-input bg-background text-foreground [&_svg]:text-muted-foreground"
                >
                  <SelectValue placeholder="选择检修等级" />
                </SelectTrigger>
                <SelectContent
                  position="popper"
                  className="z-[200] border-border bg-popover text-popover-foreground shadow-xl"
                >
                  <SelectItem
                    value="routine"
                    className="cursor-pointer text-foreground focus:bg-accent focus:text-accent-foreground data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                  >
                    例行 (routine)
                  </SelectItem>
                  <SelectItem
                    value="standard"
                    className="cursor-pointer text-foreground focus:bg-accent focus:text-accent-foreground data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                  >
                    标准 (standard)
                  </SelectItem>
                  <SelectItem
                    value="emergency"
                    className="cursor-pointer text-foreground focus:bg-accent focus:text-accent-foreground data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                  >
                    紧急 (emergency)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="tasks-symptom" className="text-foreground">
                故障现象 / 观察说明 <span className="text-red-400">*</span>
              </Label>
              <Textarea
                id="tasks-symptom"
                name="symptom_description"
                placeholder="例如：振动异常、温升过快、或需建立基线的接入说明"
                value={symptomDescription}
                onChange={(e) => setSymptomDescription(e.target.value)}
                rows={3}
                className="app-textarea min-h-[88px]"
              />
            </div>
            {createTaskError ? (
              <p className="text-sm text-red-400" role="alert">
                {createTaskError}
              </p>
            ) : null}
            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                type="button"
                variant="outline"
                className="border-border bg-transparent text-foreground hover:bg-muted"
                onClick={() => setCreateTaskOpen(false)}
                disabled={createTaskSubmitting}
              >
                取消
              </Button>
              <Button
                type="submit"
                className="bg-[#5e6ad2] text-white hover:bg-[#6b77db]"
                disabled={createTaskSubmitting}
              >
                {createTaskSubmitting ? "提交中…" : "确认创建"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleteDialogOpen}
        onOpenChange={(v) => {
          if (deleteSubmitting) return;
          setDeleteDialogOpen(v);
          if (!v) {
            setDeleteTargetId(null);
            setDeleteError(null);
          }
        }}
      >
        <DialogContent className="max-w-md border-border bg-popover text-popover-foreground">
          <DialogHeader>
            <DialogTitle>确认删除任务</DialogTitle>
            <DialogDescription>
              {deleteTargetId ? (
                <>
                  你将删除任务 <span className="font-mono text-foreground">#{deleteTargetId}</span>。
                  该操作会同步删除后端数据，且不可撤销。
                </>
              ) : (
                "该操作会同步删除后端数据，且不可撤销。"
              )}
            </DialogDescription>
          </DialogHeader>

          {deleteError ? (
            <p className="text-sm text-red-400" role="alert">
              {deleteError}
            </p>
          ) : null}

          <DialogFooter className="gap-3 sm:gap-3">
            <Button
              type="button"
              variant="outline"
              className="border-border bg-transparent text-foreground hover:bg-muted"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleteSubmitting}
            >
              取消
            </Button>
            <Button
              type="button"
              className="bg-red-500 text-white hover:bg-red-600"
              onClick={() => void confirmDelete()}
              disabled={deleteSubmitting}
            >
              {deleteSubmitting ? "删除中…" : "确认删除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

