"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  createMaintenanceCase,
  deleteMaintenanceCase,
  fetchCasesList,
  importKnowledgeDocument,
} from "@/features/cases/api"
import { toast } from "sonner"
import {
  Search,
  Filter,
  Plus,
  LayoutGrid,
  List,
  ChevronDown,
  Clock,
  Cpu,
  XCircle,
  RefreshCw,
  BookOpen,
  Wrench,
  Zap,
  ThermometerSun,
  Trash2,
  UploadCloud,
} from "lucide-react"
import { Header } from "@/shared/components/brand/app-header"
import { DEMO_MODE_CHANGED_EVENT } from "@/shared/lib/demo-mode"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog"
import { Button } from "@/shared/components/ui/button"
import { Checkbox } from "@/shared/components/ui/checkbox"
import { Input } from "@/shared/components/ui/input"
import { Label } from "@/shared/components/ui/label"
import { Textarea } from "@/shared/components/ui/textarea"

// 类型定义
type ViewMode = "grid" | "table"
type PageState = "normal" | "loading" | "empty" | "error"
type FaultLevel = "low" | "medium" | "urgent"
type VerifyStatus = "verified" | "pending" | "rejected"
type KnowledgeType = "manual" | "case" | "sop" | "expert"
type SourceType = "manual" | "diagnosis" | "import" | "human"

interface FaultCase {
  caseId: number
  id: string
  title: string
  deviceName: string
  deviceType: string
  faultTags: string[]
  summary: string
  faultLevel: FaultLevel
  verifyStatus: VerifyStatus
  updatedAt: string
  viewCount: number
  useCount: number
  knowledgeType: KnowledgeType
  sourceType: SourceType
  rootCause?: string
  resolution?: string
}

// 故障等级配置
const faultLevelConfig: Record<FaultLevel, { label: string; className: string }> = {
  low: {
    label: "例行",
    className: "bg-blue-500/15 text-blue-400 border-blue-500/20",
  },
  medium: {
    label: "标准",
    className: "bg-amber-500/15 text-amber-400 border-amber-500/20",
  },
  urgent: {
    label: "紧急",
    className: "bg-red-500/15 text-red-400 border-red-500/20",
  },
}

// 验证状态配置
const verifyStatusConfig: Record<VerifyStatus, { label: string; dotColor: string; textColor: string }> = {
  verified: {
    label: "已验证",
    dotColor: "bg-emerald-400",
    textColor: "text-emerald-400",
  },
  pending: {
    label: "待验证",
    dotColor: "bg-amber-400",
    textColor: "text-amber-400",
  },
  rejected: {
    label: "已驳回",
    dotColor: "bg-red-400",
    textColor: "text-red-400",
  },
}

// 设备类型图标
const deviceTypeIcons: Record<string, typeof Cpu> = {
  电机: Zap,
  变频器: Cpu,
  PLC: Cpu,
  液压设备: Wrench,
  传感器: ThermometerSun,
  气动元件: Wrench,
}

// 故障标签组件
function FaultTag({ label }: { label: string }) {
  return (
    <span className="app-chip-muted">
      {label}
    </span>
  )
}

// 故障等级标签
function LevelBadge({ level }: { level: FaultLevel }) {
  const config = faultLevelConfig[level]
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${config.className}`}>
      {config.label}
    </span>
  )
}

function mapCasePriorityToLevel(priority: string | null | undefined): FaultLevel {
  const normalized = String(priority || "").trim().toLowerCase()
  if (normalized === "urgent" || normalized === "high") return "urgent"
  if (normalized === "low" || normalized === "routine") return "low"
  return "medium"
}

// 验证状态指示器
function VerifyIndicator({ status }: { status: VerifyStatus }) {
  const config = verifyStatusConfig[status]
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
      <span className={`text-xs ${config.textColor}`}>{config.label}</span>
    </div>
  )
}

function formatCaseUpdatedAt(updatedAt: string) {
  return updatedAt.split(" ")[0] || "--"
}

// 案例卡片组件
function CaseCard({
  caseData,
  onDelete,
}: {
  caseData: FaultCase
  onDelete: (caseData: FaultCase) => void
}) {
  const DeviceIcon = deviceTypeIcons[caseData.deviceType] || Cpu

  return (
    <Link href={`/cases/${caseData.id}`}>
      <div className="group relative h-full cursor-pointer rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:bg-muted/45 hover:border-border-strong">
        {/* 发光边框效果 */}
        <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" 
          style={{
            boxShadow: "inset 0 0 0 1px rgba(94,106,210,0.15), 0 0 20px rgba(94,106,210,0.05)"
          }}
        />
        
        {/* 头部 */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-muted">
              <DeviceIcon className="w-4 h-4 text-muted-foreground" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">{caseData.deviceType}</p>
              <p className="text-xs text-foreground">{caseData.deviceName}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <LevelBadge level={caseData.faultLevel} />
            <button
              type="button"
              aria-label={`删除案例 ${caseData.title}`}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-muted hover:text-red-400"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                onDelete(caseData)
              }}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* 标题 */}
        <h3 className="mb-2 line-clamp-2 font-medium text-foreground transition-colors group-hover:text-[#5e6ad2]">
          {caseData.title}
        </h3>

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="app-chip-muted">
            {caseData.knowledgeType === "manual"
              ? "手册"
              : caseData.knowledgeType === "case"
                ? "案例"
                : caseData.knowledgeType === "sop"
                  ? "SOP"
                  : "专家经验"}
          </span>
          <span className="app-chip-muted text-muted-foreground">
            来源:{caseData.sourceType === "diagnosis" ? "诊断沉淀" : caseData.sourceType === "import" ? "系统导入" : caseData.sourceType === "manual" ? "手册" : "人工"}
          </span>
        </div>

        {/* 标签 */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {caseData.faultTags.slice(0, 3).map((tag) => (
            <FaultTag key={tag} label={tag} />
          ))}
          {caseData.faultTags.length > 3 && (
            <span className="text-xs text-muted-foreground">+{caseData.faultTags.length - 3}</span>
          )}
        </div>

        {/* 摘要 */}
        <div className="space-y-2 mb-4">
          <p className="line-clamp-2 text-xs text-muted-foreground">
            <span className="text-foreground">故障现象：</span>
            {caseData.summary}
          </p>
          {caseData.rootCause ? (
            <p className="line-clamp-2 text-xs text-muted-foreground">
              <span className="text-foreground">根因分析：</span>
              {caseData.rootCause}
            </p>
          ) : null}
          {caseData.resolution ? (
            <p className="line-clamp-2 text-xs text-muted-foreground">
              <span className="text-foreground">处理方案：</span>
              {caseData.resolution}
            </p>
          ) : null}
        </div>

        {/* 底部信息 */}
        <div className="flex items-center justify-between border-t border-border pt-3">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatCaseUpdatedAt(caseData.updatedAt)}
            </span>
          </div>
          <VerifyIndicator status={caseData.verifyStatus} />
        </div>
      </div>
    </Link>
  )
}

// 表格行组件
function CaseTableRow({
  caseData,
  onDelete,
}: {
  caseData: FaultCase
  onDelete: (caseData: FaultCase) => void
}) {
  const DeviceIcon = deviceTypeIcons[caseData.deviceType] || Cpu

  return (
    <Link href={`/cases/${caseData.id}`}>
      <div className="group grid grid-cols-12 cursor-pointer items-center gap-4 border-b border-border px-4 py-3 transition-colors hover:bg-muted/45">
        {/* 案例信息 */}
        <div className="col-span-3 flex items-center gap-3">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-border bg-muted">
            <DeviceIcon className="w-4 h-4 text-muted-foreground" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm text-foreground transition-colors group-hover:text-[#5e6ad2]">
              {caseData.title}
            </p>
            <p className="truncate text-xs text-muted-foreground">{caseData.deviceName}</p>
          </div>
        </div>

        {/* 标签 */}
        <div className="col-span-3 flex flex-wrap gap-1">
          {caseData.faultTags.slice(0, 2).map((tag) => (
            <FaultTag key={tag} label={tag} />
          ))}
          {caseData.faultTags.length > 2 && (
            <span className="text-xs text-muted-foreground">+{caseData.faultTags.length - 2}</span>
          )}
        </div>

        {/* 等级 */}
        <div className="col-span-1">
          <LevelBadge level={caseData.faultLevel} />
        </div>

        {/* 验证状态 */}
        <div className="col-span-2">
          <VerifyIndicator status={caseData.verifyStatus} />
        </div>

        {/* 更新时间 */}
        <div className="col-span-2 text-right">
          <span className="text-sm text-muted-foreground">{formatCaseUpdatedAt(caseData.updatedAt)}</span>
        </div>

        {/* 操作 */}
        <div className="col-span-1 flex justify-end">
          <button
            type="button"
            aria-label={`删除案例 ${caseData.title}`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-muted hover:text-red-400"
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
              onDelete(caseData)
            }}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </Link>
  )
}

// 骨架卡片
function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <div className="app-skeleton h-8 w-8 rounded-lg" />
          <div>
            <div className="app-skeleton mb-1 h-3 w-12" />
            <div className="app-skeleton h-3 w-20" />
          </div>
        </div>
        <div className="app-skeleton h-5 w-12" />
      </div>
      <div className="app-skeleton mb-3 h-5 w-3/4" />
      <div className="flex gap-1.5 mb-3">
        <div className="app-skeleton h-5 w-16 rounded-full" />
        <div className="app-skeleton h-5 w-14 rounded-full" />
      </div>
      <div className="space-y-2 mb-4">
        <div className="app-skeleton h-4 w-full" />
        <div className="app-skeleton h-4 w-2/3" />
      </div>
      <div className="flex justify-between border-t border-border pt-3">
        <div className="app-skeleton h-4 w-24" />
        <div className="app-skeleton h-4 w-16" />
      </div>
    </div>
  )
}

// 骨架表格行
function SkeletonTableRow() {
  return (
    <div className="grid grid-cols-12 gap-4 border-b border-border px-4 py-3">
      <div className="col-span-3 flex items-center gap-3">
        <div className="app-skeleton h-8 w-8 rounded-lg" />
        <div className="flex-1">
          <div className="app-skeleton mb-1 h-4 w-3/4" />
          <div className="app-skeleton h-3 w-1/2" />
        </div>
      </div>
      <div className="col-span-3 flex gap-1">
        <div className="app-skeleton h-5 w-14 rounded-full" />
        <div className="app-skeleton h-5 w-12 rounded-full" />
      </div>
      <div className="col-span-1">
        <div className="app-skeleton h-5 w-12" />
      </div>
      <div className="col-span-2">
        <div className="app-skeleton h-4 w-16" />
      </div>
      <div className="col-span-2 flex justify-end">
        <div className="app-skeleton h-4 w-20" />
      </div>
      <div className="col-span-1 flex justify-end">
        <div className="app-skeleton h-8 w-8 rounded-md" />
      </div>
    </div>
  )
}

// 空状态组件
function EmptyState({ onCreateClick }: { onCreateClick?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="app-empty-icon mb-4 h-16 w-16">
        <BookOpen className="w-8 h-8" />
      </div>
      <h3 className="mb-2 text-lg font-medium text-foreground">暂无故障案例</h3>
      <p className="mb-6 max-w-sm text-center text-sm text-muted-foreground">
        案例库为空，开始创建您的第一个故障案例，沉淀宝贵的运维经验
      </p>
      <button
        type="button"
        onClick={onCreateClick}
        className="inline-flex items-center gap-2 px-4 py-2 bg-[#5e6ad2] hover:bg-[#7170ff] text-white text-sm font-medium rounded-md transition-colors"
      >
        <Plus className="w-4 h-4" />
        创建首个故障案例
      </button>
    </div>
  )
}

// 错误状态组件
function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center">
          <XCircle className="w-5 h-5 text-red-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">加载失败</p>
          <p className="text-xs text-muted-foreground">无法获取案例列表，请检查网络连接后重试</p>
        </div>
      </div>
      <button
        onClick={onRetry}
        className="app-btn-secondary"
      >
        <RefreshCw className="w-4 h-4" />
        重试
      </button>
    </div>
  )
}

// 筛选下拉菜单
function FilterDropdown({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const selectedOption = options.find((opt) => opt.value === value)

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
      >
        <span className="text-muted-foreground">{label}:</span>
        <span>{selectedOption?.label || "全部"}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="app-overlay-panel absolute left-0 top-full z-20 mt-1 w-40 py-1 shadow-xl">
            {options.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  onChange(option.value)
                  setIsOpen(false)
                }}
                className={`w-full px-3 py-2 text-left text-sm transition-colors hover:bg-muted ${
                  value === option.value ? "text-[#5e6ad2]" : "text-foreground"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// 主页面组件
export default function CasesPage() {
  const router = useRouter()
  const [viewMode, setViewMode] = useState<ViewMode>("grid")
  const [pageState, setPageState] = useState<PageState>("normal")
  const [searchQuery, setSearchQuery] = useState("")
  const [levelFilter, setLevelFilter] = useState("all")
  const [verifyFilter, setVerifyFilter] = useState("all")
  const [knowledgeTypeFilter, setKnowledgeTypeFilter] = useState("all")
  const [sourceTypeFilter, setSourceTypeFilter] = useState("all")
  const [moreFiltersOpen, setMoreFiltersOpen] = useState(false)
  const [apiCases, setApiCases] = useState<FaultCase[]>([])

  const [createOpen, setCreateOpen] = useState(false)
  const [createSubmitting, setCreateSubmitting] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<FaultCase | null>(null)
  const [deleteSubmitting, setDeleteSubmitting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [uploadDrawerOpen, setUploadDrawerOpen] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadEquipmentType, setUploadEquipmentType] = useState("")
  const [uploadKnowledgeType, setUploadKnowledgeType] = useState<KnowledgeType>("manual")
  const [uploadTitle, setUploadTitle] = useState("")
  const [uploadReplaceExisting, setUploadReplaceExisting] = useState(true)
  const [uploadSubmitting, setUploadSubmitting] = useState(false)
  const [newTitle, setNewTitle] = useState("")
  const [newEquipmentType, setNewEquipmentType] = useState("")
  const [newEquipmentModel, setNewEquipmentModel] = useState("")
  const [newFaultType, setNewFaultType] = useState("")
  const [newSymptom, setNewSymptom] = useState("")
  const [newSteps, setNewSteps] = useState("")
  const [newResolution, setNewResolution] = useState("")
  const [newWorkOrderId, setNewWorkOrderId] = useState("")
  const [newPriority, setNewPriority] = useState<"low" | "medium" | "urgent">("medium")

  const resetUploadForm = useCallback(() => {
    setUploadFile(null)
    setUploadEquipmentType("")
    setUploadKnowledgeType("manual")
    setUploadTitle("")
    setUploadReplaceExisting(true)
  }, [])

  const resetCreateForm = useCallback(() => {
    setCreateError(null)
    setNewTitle("")
    setNewEquipmentType("")
    setNewEquipmentModel("")
    setNewFaultType("")
    setNewSymptom("")
    setNewSteps("")
    setNewResolution("")
    setNewWorkOrderId("")
    setNewPriority("medium")
  }, [])

  const loadCases = useCallback(async () => {
    try {
      const r = await fetchCasesList({ limit: 50 })
      const pickType = (c: { report_source?: string | null }): KnowledgeType => {
        const src = (c.report_source || "").toLowerCase()
        if (src.includes("manual") || src.includes("手册")) return "manual"
        if (src.includes("case") || src.includes("案例")) return "case"
        if (src.includes("sop")) return "sop"
        return "expert"
      }
      const pickSource = (c: { report_source?: string | null }): SourceType => {
        const src = (c.report_source || "").toLowerCase()
        if (src.includes("diagnosis") || src.includes("诊断")) return "diagnosis"
        if (src.includes("import") || src.includes("导入")) return "import"
        if (src.includes("manual") || src.includes("手册")) return "manual"
        return "human"
      }
      const mapped: FaultCase[] = r.cases.map((c) => ({
        caseId: c.id,
        id: `CASE-${c.id}`,
        title: c.title,
        deviceName: c.equipment_type,
        deviceType: c.equipment_type,
        faultTags: String(c.symptom_description || c.title)
          .split(/[，,、\s]+/)
          .map((s) => s.trim())
          .filter(Boolean)
          .slice(0, 4),
        summary: c.symptom_description || c.title,
        faultLevel: mapCasePriorityToLevel(c.priority),
        verifyStatus:
          c.status === "approved"
            ? "verified"
            : c.status === "rejected"
              ? "rejected"
              : "pending",
        updatedAt: c.updated_at ? String(c.updated_at).replace("T", " ").slice(0, 16) : "",
        viewCount: 0,
        useCount: 0,
        knowledgeType: pickType(c),
        sourceType: pickSource(c),
        rootCause: undefined,
        resolution: undefined,
      }))
      setApiCases(mapped)
      setPageState(mapped.length ? "normal" : "empty")
    } catch {
      setPageState("error")
    }
  }, [])

  useEffect(() => {
    void loadCases()
  }, [loadCases])

  const confirmDeleteCase = useCallback(async () => {
    if (!deleteTarget) return
    setDeleteSubmitting(true)
    setDeleteError(null)
    try {
      await deleteMaintenanceCase(deleteTarget.caseId)
      toast.success("案例已删除")
      setDeleteTarget(null)
      await loadCases()
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "删除失败，请稍后重试。")
    } finally {
      setDeleteSubmitting(false)
    }
  }, [deleteTarget, loadCases])

  useEffect(() => {
    const handleModeChanged = () => {
      void loadCases()
    }
    window.addEventListener(DEMO_MODE_CHANGED_EVENT, handleModeChanged as EventListener)
    return () => {
      window.removeEventListener(DEMO_MODE_CHANGED_EVENT, handleModeChanged as EventListener)
    }
  }, [loadCases])

  const submitCreateCase = useCallback(async () => {
    setCreateError(null)
    const title = newTitle.trim()
    const equipment_type = newEquipmentType.trim()
    const symptom_description = newSymptom.trim()
    if (!title || !equipment_type || !symptom_description) {
      setCreateError("请填写案例标题、设备类型与故障现象。")
      return
    }
    const processing_steps = newSteps
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
    const resolution_summary = newResolution.trim() || null
    if (!processing_steps.length && !resolution_summary) {
      setCreateError("请填写「处理步骤」或「处理结果总结」至少一项。")
      return
    }
    setCreateSubmitting(true)
    try {
      const created = await createMaintenanceCase({
        title,
        equipment_type,
        symptom_description,
        processing_steps,
        resolution_summary,
        equipment_model: newEquipmentModel.trim() || null,
        fault_type: newFaultType.trim() || null,
        work_order_id: newWorkOrderId.trim() || null,
        asset_code: null,
        report_source: "manual",
        priority: newPriority,
      })
      setCreateOpen(false)
      resetCreateForm()
      await loadCases()
      router.push(`/cases/CASE-${created.id}`)
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "创建失败，请稍后重试。")
    } finally {
      setCreateSubmitting(false)
    }
  }, [
    newTitle,
    newEquipmentType,
    newSymptom,
    newSteps,
    newResolution,
    newEquipmentModel,
    newFaultType,
    newWorkOrderId,
    newPriority,
    loadCases,
    router,
    resetCreateForm,
  ])

  const createCaseEquipmentSuggestions = [
    "摩托车发动机",
    "点火系统",
    "燃油供给系统",
    "润滑系统",
    "冷却系统",
    "离合器总成",
    "变速机构",
  ]

  const createCaseFaultSuggestions = [
    "无法启动",
    "异响",
    "过热",
    "漏油",
    "动力不足",
    "抖动",
    "冒黑烟",
  ]

  const levelOptions = [
    { value: "all", label: "全部" },
    { value: "low", label: "例行" },
    { value: "medium", label: "标准" },
    { value: "urgent", label: "紧急" },
  ]

  const verifyOptions = [
    { value: "all", label: "全部" },
    { value: "verified", label: "已验证" },
    { value: "pending", label: "待验证" },
    { value: "rejected", label: "已驳回" },
  ]

  const knowledgeTypeOptions = [
    { value: "all", label: "全部" },
    { value: "manual", label: "手册" },
    { value: "case", label: "案例" },
    { value: "sop", label: "SOP" },
    { value: "expert", label: "专家经验" },
  ]

  const sourceTypeOptions = [
    { value: "all", label: "全部" },
    { value: "diagnosis", label: "诊断沉淀" },
    { value: "import", label: "系统导入" },
    { value: "human", label: "人工上传" },
    { value: "manual", label: "手册" },
  ]

  const sourceCases = apiCases

  const filterLabelMap = {
    level: levelOptions.find((o) => o.value === levelFilter)?.label ?? "全部",
    verify: verifyOptions.find((o) => o.value === verifyFilter)?.label ?? "全部",
    knowledgeType: knowledgeTypeOptions.find((o) => o.value === knowledgeTypeFilter)?.label ?? "全部",
    sourceType: sourceTypeOptions.find((o) => o.value === sourceTypeFilter)?.label ?? "全部",
  }

  const selectedFilterChips = [
    levelFilter !== "all" ? { key: "level", label: `故障等级：${filterLabelMap.level}` } : null,
    verifyFilter !== "all" ? { key: "verify", label: `验证状态：${filterLabelMap.verify}` } : null,
    knowledgeTypeFilter !== "all" ? { key: "knowledgeType", label: `知识类型：${filterLabelMap.knowledgeType}` } : null,
    sourceTypeFilter !== "all" ? { key: "sourceType", label: `来源：${filterLabelMap.sourceType}` } : null,
  ].filter(Boolean) as Array<{ key: string; label: string }>

  const clearAllFilters = () => {
    setLevelFilter("all")
    setVerifyFilter("all")
    setKnowledgeTypeFilter("all")
    setSourceTypeFilter("all")
    setSearchQuery("")
  }

  const submitKnowledgeUpload = useCallback(() => {
    if (!uploadFile) {
      toast.error("请先选择上传文件")
      return
    }
    if (!uploadEquipmentType.trim()) {
      toast.error("请填写设备类型")
      return
    }

    void (async () => {
      setUploadSubmitting(true)
      try {
        const payload = await importKnowledgeDocument({
          file: uploadFile,
          equipment_type: uploadEquipmentType.trim(),
          title: uploadTitle.trim() || undefined,
          source_type: uploadKnowledgeType,
          replace_existing: uploadReplaceExisting,
        })
        setUploadDrawerOpen(false)
        resetUploadForm()
        router.push(`/knowledge?from=cases&highlightImportJob=${payload.id}`)
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "上传失败，请稍后重试")
      } finally {
        setUploadSubmitting(false)
      }
    })()
  }, [resetUploadForm, router, uploadEquipmentType, uploadFile, uploadKnowledgeType, uploadReplaceExisting, uploadTitle])

  // 过滤数据
  const filteredCases = sourceCases.filter((c) => {
    if (searchQuery && !c.title.includes(searchQuery) && !c.deviceName.includes(searchQuery) && !c.faultTags.some((t) => t.includes(searchQuery))) {
      return false
    }
    if (levelFilter !== "all" && c.faultLevel !== levelFilter) return false
    if (verifyFilter !== "all" && c.verifyStatus !== verifyFilter) return false
    if (knowledgeTypeFilter !== "all" && c.knowledgeType !== knowledgeTypeFilter) return false
    if (sourceTypeFilter !== "all" && c.sourceType !== sourceTypeFilter) return false
    return true
  })

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="app-main">
        {/* 页面标题区 */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-foreground mb-1">知识案例库</h1>
            <p className="text-sm text-muted-foreground">
              沉淀历史故障案例、检修经验与标准作业知识 · 共 {sourceCases.length} 条 · 已验证{" "}
              {sourceCases.filter((c) => c.verifyStatus === "verified").length} 条
            </p>
          </div>
        </div>

        {/* 操作栏 */}
        <div className="app-card p-3.5 mb-6">
          <div className="flex flex-col gap-3">
            {/* 第一行：搜索 + 核心筛选 */}
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="relative w-full min-w-[300px] max-w-[420px] xl:min-w-[360px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="搜索错误码、设备型号、故障现象、根因关键词..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="app-input h-9 w-full pl-10 pr-4"
                />
              </div>

              <FilterDropdown
                label="故障等级"
                options={levelOptions}
                value={levelFilter}
                onChange={setLevelFilter}
              />
              <FilterDropdown
                label="验证状态"
                options={verifyOptions}
                value={verifyFilter}
                onChange={setVerifyFilter}
              />

              <div className="relative">
                <button
                  type="button"
                  onClick={() => setMoreFiltersOpen((v) => !v)}
                  className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-card px-3 text-sm text-foreground transition-colors hover:bg-muted"
                >
                  <Filter className="w-3.5 h-3.5 text-muted-foreground" />
                  更多筛选
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${moreFiltersOpen ? "rotate-180" : ""}`} />
                </button>
                {moreFiltersOpen ? (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setMoreFiltersOpen(false)} />
                    <div className="absolute right-0 top-full z-20 mt-2 w-[260px] rounded-xl border border-border bg-popover p-3 shadow-2xl">
                      <div className="space-y-2.5">
                        <div>
                          <div className="mb-1 text-xs text-muted-foreground">知识类型</div>
                          <div className="grid grid-cols-2 gap-1.5">
                            {knowledgeTypeOptions.map((opt) => {
                              const active = knowledgeTypeFilter === opt.value
                              return (
                                <button
                                  key={opt.value}
                                  type="button"
                                  onClick={() => setKnowledgeTypeFilter(opt.value)}
                                  className={`h-8 rounded-md border text-xs transition-colors ${
                                    active
                                      ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-[#22c55e]/45 dark:bg-[#22c55e]/15 dark:text-[#86efac]"
                                      : "border-border bg-card text-foreground hover:bg-muted"
                                  }`}
                                >
                                  {opt.label}
                                </button>
                              )
                            })}
                          </div>
                        </div>
                        <div>
                          <div className="mb-1 text-xs text-muted-foreground">来源</div>
                          <div className="grid grid-cols-2 gap-1.5">
                            {sourceTypeOptions.map((opt) => {
                              const active = sourceTypeFilter === opt.value
                              return (
                                <button
                                  key={opt.value}
                                  type="button"
                                  onClick={() => setSourceTypeFilter(opt.value)}
                                  className={`h-8 rounded-md border text-xs transition-colors ${
                                    active
                                      ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-[#22c55e]/45 dark:bg-[#22c55e]/15 dark:text-[#86efac]"
                                      : "border-border bg-card text-foreground hover:bg-muted"
                                  }`}
                                >
                                  {opt.label}
                                </button>
                              )
                            })}
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                ) : null}
              </div>

            </div>

            {/* 第二行：当前筛选 + 操作按钮（紧凑） */}
            <div className="flex min-h-9 flex-wrap items-center justify-between gap-2 border-t border-border pt-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted-foreground">当前筛选：</span>
                {selectedFilterChips.length > 0 ? (
                  <>
                    {selectedFilterChips.map((chip) => (
                      <span
                        key={chip.key}
                        className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2.5 py-1 text-xs text-foreground"
                      >
                        {chip.label}
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground"
                          onClick={() => {
                            if (chip.key === "level") setLevelFilter("all")
                            if (chip.key === "verify") setVerifyFilter("all")
                            if (chip.key === "knowledgeType") setKnowledgeTypeFilter("all")
                            if (chip.key === "sourceType") setSourceTypeFilter("all")
                          }}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <button
                      type="button"
                      onClick={clearAllFilters}
                      className="text-xs text-muted-foreground transition-colors hover:text-foreground"
                    >
                      清空筛选
                    </button>
                  </>
                ) : (
                  <span className="text-xs text-[#5f6672]">全部案例</span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setUploadDrawerOpen(true)}
                  className="inline-flex h-8 items-center gap-2 rounded-md border border-border bg-transparent px-3 text-sm text-foreground transition-colors hover:bg-muted"
                >
                  <BookOpen className="w-4 h-4" />
                  <span className="hidden sm:inline">知识文档上传</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    resetCreateForm()
                    setCreateOpen(true)
                  }}
                  className="inline-flex h-8 items-center gap-2 rounded-md bg-[#16a34a] px-4 text-sm font-medium text-white transition-colors hover:bg-[#15803d]"
                >
                  <Plus className="w-4 h-4" />
                  <span className="hidden sm:inline">新建案例</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 结果区标题 */}
        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            案例列表 <span className="ml-1 text-foreground">共 {filteredCases.length} 条</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">视图：</span>
            <div className="flex items-center rounded-md border border-border bg-card p-0.5">
              <button
                onClick={() => setViewMode("grid")}
                className={`p-1.5 rounded transition-colors ${
                  viewMode === "grid"
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                  onClick={() => setViewMode("table")}
                  className={`p-1.5 rounded transition-colors ${
                    viewMode === "table"
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* 错误状态 */}
        {pageState === "error" && (
          <div className="mb-6">
            <ErrorState onRetry={() => void loadCases()} />
          </div>
        )}

        {/* 内容区域 */}
        {pageState === "empty" ? (
          <EmptyState
            onCreateClick={() => {
              resetCreateForm()
              setCreateOpen(true)
            }}
          />
        ) : pageState === "loading" ? (
          viewMode === "grid" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : (
            <div className="app-card overflow-hidden">
              <div className="app-table-head grid grid-cols-12 gap-4 border-b border-border px-4 py-3 text-xs font-medium">
                <div className="col-span-3">案例信息</div>
                <div className="col-span-3">故障标签</div>
                <div className="col-span-1">等级</div>
                <div className="col-span-2">验证状态</div>
                <div className="col-span-2 text-right">更新时间</div>
                <div className="col-span-1 text-right">操作</div>
              </div>
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonTableRow key={i} />
              ))}
            </div>
          )
        ) : viewMode === "grid" ? (
          filteredCases.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredCases.map((caseData) => (
                <CaseCard key={caseData.id} caseData={caseData} onDelete={setDeleteTarget} />
              ))}
            </div>
          ) : (
            <EmptyState
              onCreateClick={() => {
                resetCreateForm()
                setCreateOpen(true)
              }}
            />
          )
        ) : (
          <div className="app-card overflow-hidden">
            {/* 表头 */}
            <div className="app-table-head hidden grid-cols-12 gap-4 border-b border-border px-4 py-3 text-xs font-medium lg:grid">
              <div className="col-span-3">案例信息</div>
              <div className="col-span-3">故障标签</div>
              <div className="col-span-1">等级</div>
              <div className="col-span-2">验证状态</div>
              <div className="col-span-2 text-right">更新时间</div>
              <div className="col-span-1 text-right">操作</div>
            </div>

            {/* 表格内容 - 桌面端 */}
            <div className="hidden lg:block">
              {filteredCases.length > 0 ? (
                filteredCases.map((caseData) => (
                  <CaseTableRow key={caseData.id} caseData={caseData} onDelete={setDeleteTarget} />
                ))
              ) : (
                <EmptyState
                  onCreateClick={() => {
                    resetCreateForm()
                    setCreateOpen(true)
                  }}
                />
              )}
            </div>

            {/* 移动端卡片列表 */}
            <div className="divide-y divide-border lg:hidden">
              {filteredCases.length > 0 ? (
                filteredCases.map((caseData) => (
                  <CaseCard key={caseData.id} caseData={caseData} onDelete={setDeleteTarget} />
                ))
              ) : (
                <EmptyState
                  onCreateClick={() => {
                    resetCreateForm()
                    setCreateOpen(true)
                  }}
                />
              )}
            </div>
          </div>
        )}

        {/* 分页 */}
        {pageState === "normal" && filteredCases.length > 0 && (
          <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">
              显示 1-{filteredCases.length} 条，共 {filteredCases.length} 条
            </p>
            <div className="flex items-center gap-1">
              <button className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50" disabled>
                上一页
              </button>
              <button className="px-3 py-1.5 text-sm bg-[#5e6ad2] text-white rounded-md">1</button>
              <button className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50" disabled>
                下一页
              </button>
            </div>
          </div>
        )}
      </main>

      <Dialog
        open={uploadDrawerOpen}
        onOpenChange={(open) => {
          setUploadDrawerOpen(open)
          if (!open && !uploadSubmitting) {
            resetUploadForm()
          }
        }}
      >
        <DialogContent className="left-auto right-0 top-0 h-screen w-full max-w-xl translate-x-0 translate-y-0 rounded-none border-y-0 border-r-0 border-l border-border bg-popover p-0 text-popover-foreground data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right">
          <div className="h-full overflow-y-auto p-6">
            <DialogHeader>
              <DialogTitle>知识文档上传</DialogTitle>
              <DialogDescription>
                在案例库内完成上传，保持当前上下文不跳转页面。
              </DialogDescription>
            </DialogHeader>

            <div className="mt-5 space-y-4">
              <button
                type="button"
                onClick={() => document.getElementById("cases-knowledge-upload-input")?.click()}
                className="w-full rounded-lg border border-dashed border-border bg-muted px-4 py-6 text-left transition-colors hover:bg-muted/80"
              >
                <div className="flex items-center gap-2 text-foreground">
                  <UploadCloud className="h-4 w-4" />
                  <span className="text-sm">拖拽 PDF / 图片到此处，或点击选择文件</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">支持 PDF、PNG、JPG、WEBP。</p>
              </button>
              <input
                id="cases-knowledge-upload-input"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                className="hidden"
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              />
              {uploadFile ? <p className="text-xs text-muted-foreground">已选择：{uploadFile.name}</p> : null}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label className="text-foreground">设备类型 *</Label>
                  <Input
                    value={uploadEquipmentType}
                    onChange={(e) => setUploadEquipmentType(e.target.value)}
                    placeholder="如：摩托车发动机"
                    className="app-input"
                  />
                </div>
                <div className="grid gap-2">
                  <Label className="text-foreground">知识类型 *</Label>
                  <select
                    value={uploadKnowledgeType}
                    onChange={(e) => setUploadKnowledgeType(e.target.value as KnowledgeType)}
                    className="app-select w-full"
                  >
                    <option value="manual">设备手册</option>
                    <option value="sop">SOP流程</option>
                    <option value="case">故障案例</option>
                    <option value="expert">专家经验</option>
                  </select>
                </div>
              </div>

              <div className="grid gap-2">
                <Label className="text-foreground">文档标题</Label>
                <Input
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="默认使用文件名"
                  className="app-input"
                />
              </div>

              <label className="flex items-start gap-3 rounded-lg border border-border bg-card px-3 py-3">
                <Checkbox
                  checked={uploadReplaceExisting}
                  onCheckedChange={(checked) => setUploadReplaceExisting(Boolean(checked))}
                  className="mt-0.5"
                />
                <div className="space-y-1">
                  <div className="text-sm text-foreground">同名文档覆盖导入</div>
                  <p className="text-xs text-muted-foreground">
                    勾选后，如知识库已存在同名文档，将删除旧文档并使用当前文件重新切分导入。
                  </p>
                </div>
              </label>

              <div className="rounded-lg border border-border bg-muted p-3 text-xs text-muted-foreground">
                上传后流程：上传成功 → 文本解析/OCR → 分段切片 → 向量化索引 → 待审核 → 入库完成
              </div>
            </div>

            <DialogFooter className="mt-6 flex items-center justify-between gap-2">
              <Link
                href="/knowledge?from=cases"
                className="text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                进入知识文档管理页
              </Link>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="border-border bg-transparent text-foreground hover:bg-muted hover:text-foreground"
                  onClick={() => {
                    setUploadDrawerOpen(false)
                    resetUploadForm()
                  }}
                >
                  取消
                </Button>
                <Button
                  type="button"
                  className="bg-[#5e6ad2] text-white hover:bg-[#6b77db]"
                  disabled={uploadSubmitting}
                  onClick={submitKnowledgeUpload}
                >
                  {uploadSubmitting ? "上传中..." : "开始上传"}
                </Button>
              </div>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (deleteSubmitting) return
          if (!open) {
            setDeleteTarget(null)
            setDeleteError(null)
          }
        }}
      >
        <AlertDialogContent className="border-border bg-popover text-popover-foreground">
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除案例</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              {deleteTarget
                ? `确定删除案例「${deleteTarget.title}」？若该案例已沉淀为知识文档，关联文档也会一并删除。`
                : "此操作不可撤销。"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deleteError ? (
            <p className="text-sm text-red-400" role="alert">
              {deleteError}
            </p>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel
              className="border-border bg-transparent text-foreground hover:bg-muted hover:text-foreground"
              disabled={deleteSubmitting}
            >
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={(event) => {
                event.preventDefault()
                void confirmDeleteCase()
              }}
            >
              {deleteSubmitting ? "删除中…" : "确认删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open)
          if (!open) setCreateError(null)
        }}
      >
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto border-border bg-popover text-popover-foreground">
          <DialogHeader>
            <DialogTitle>新建故障案例</DialogTitle>
            <DialogDescription>
              用于沉淀图片诊断、检修步骤和处理结论。请至少填写「处理步骤」或「处理结果总结」之一。
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="case-title" className="text-foreground">
                案例标题 <span className="text-red-400">*</span>
              </Label>
              <Input
                id="case-title"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="简要概括故障与处理要点"
                className="app-input"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="case-eq-type" className="text-foreground">
                  设备/部件 <span className="text-red-400">*</span>
                </Label>
                <Input
                  id="case-eq-type"
                  value={newEquipmentType}
                  onChange={(e) => setNewEquipmentType(e.target.value)}
                  list="case-equipment-suggestions"
                  placeholder="如：摩托车发动机、点火系统"
                  className="app-input"
                />
                <datalist id="case-equipment-suggestions">
                  {createCaseEquipmentSuggestions.map((item) => (
                    <option key={item} value={item} />
                  ))}
                </datalist>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="case-priority" className="text-foreground">
                  处置等级
                </Label>
                <select
                  id="case-priority"
                  value={newPriority}
                  onChange={(e) =>
                    setNewPriority(e.target.value as "low" | "medium" | "urgent")
                  }
                  className="app-select h-9 w-full"
                >
                  <option value="low">例行</option>
                  <option value="medium">标准</option>
                  <option value="urgent">紧急</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="case-model" className="text-foreground">
                  设备型号
                </Label>
                <Input
                  id="case-model"
                  value={newEquipmentModel}
                  onChange={(e) => setNewEquipmentModel(e.target.value)}
                  placeholder="如：CG125、单缸风冷"
                  className="app-input"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="case-fault-type" className="text-foreground">
                  故障类型
                </Label>
                <Input
                  id="case-fault-type"
                  value={newFaultType}
                  onChange={(e) => setNewFaultType(e.target.value)}
                  list="case-fault-suggestions"
                  placeholder="如：无法启动、异响、漏油"
                  className="app-input"
                />
                <datalist id="case-fault-suggestions">
                  {createCaseFaultSuggestions.map((item) => (
                    <option key={item} value={item} />
                  ))}
                </datalist>
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="case-wo" className="text-foreground">
                关联工单编号
              </Label>
              <Input
                id="case-wo"
                value={newWorkOrderId}
                onChange={(e) => setNewWorkOrderId(e.target.value)}
                placeholder="没有可不填"
                className="app-input"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="case-symptom" className="text-foreground">
                故障现象 <span className="text-red-400">*</span>
              </Label>
              <Textarea
                id="case-symptom"
                value={newSymptom}
                onChange={(e) => setNewSymptom(e.target.value)}
                placeholder="描述现场现象、图片线索、异常部位和影响范围"
                rows={3}
                className="app-textarea min-h-[72px] resize-y"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="case-steps" className="text-foreground">
                处理步骤（每行一条）
              </Label>
              <Textarea
                id="case-steps"
                value={newSteps}
                onChange={(e) => setNewSteps(e.target.value)}
                placeholder={"每行一条，如：\n1. 拆下右侧外壳检查点火线圈\n2. 观察火花塞积碳情况\n3. 清洗并复测启动情况"}
                rows={4}
                className="app-textarea min-h-[88px] resize-y"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="case-resolution" className="text-foreground">
                处理结果总结
              </Label>
              <Textarea
                id="case-resolution"
                value={newResolution}
                onChange={(e) => setNewResolution(e.target.value)}
                placeholder="说明最终结论、处理效果、复测结果和后续建议"
                rows={3}
                className="app-textarea min-h-[72px] resize-y"
              />
            </div>

            {createError ? (
              <p className="text-sm text-red-400" role="alert">
                {createError}
              </p>
            ) : null}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              className="border-border bg-transparent text-foreground"
              onClick={() => setCreateOpen(false)}
              disabled={createSubmitting}
            >
              取消
            </Button>
            <Button
              type="button"
              className="bg-[#5e6ad2] text-white hover:bg-[#6b77db]"
              onClick={() => void submitCreateCase()}
              disabled={createSubmitting}
            >
              {createSubmitting ? "提交中…" : "提交案例"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

