"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Activity, AlertCircle, Server, CheckCircle, RefreshCw, FileCheck, Layers } from "lucide-react"
import { toast } from "sonner"
import {
  fetchWorkbenchOverview,
  fetchSystemMetrics,
  fetchHealth,
  fetchTaskExport,
  deleteMaintenanceTask,
  downloadJsonInBrowser,
  type WorkbenchOverview,
} from "@/features/dashboard/api"
import { fetchCasesList } from "@/features/cases/api"
import { getMaintenanceToken } from "@/features/auth/lib/token-store"
import { fetchMaintenanceHistory, fetchTaskDetail } from "@/features/tasks/api"
import { listWorkOrders } from "@/features/tickets/api"
import type { FaultRecord } from "@/features/dashboard/components/fault-table"
import { Header } from "@/shared/components/brand/app-header"
import { StatCard } from "@/features/dashboard/components/stat-card"
import { FaultTable } from "@/features/dashboard/components/fault-table"
import { Timeline } from "@/features/dashboard/components/timeline"
import { DeviceGrid } from "@/features/dashboard/components/device-card"
import { TrendChartCard, DonutChart } from "@/features/dashboard/components/charts"
import { EmptyState, ErrorState } from "@/features/dashboard/components/empty-state"
import { DashboardSkeleton } from "@/features/dashboard/components/skeleton"
import { Button } from "@/shared/components/ui/button"
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
import { formatDateTimeLocal } from "@/shared/lib/utils"
import { DEMO_MODE_CHANGED_EVENT } from "@/shared/lib/demo-mode"

interface RuntimeSnapshot {
  counters?: Array<{ name?: string; labels?: Record<string, string>; value?: number }>
  durations?: Array<{ name?: string; labels?: Record<string, string>; count?: number; avg_ms?: number }>
}

function normalizeFaultStatus(rawStatus: string): FaultRecord["status"] {
  const st = String(rawStatus || "").toLowerCase()
  if (["pending", "open"].includes(st)) return "pending"
  if (["in_progress", "processing"].includes(st)) return "processing"
  if (["resolved", "closed", "done", "complete", "completed"].includes(st)) return "resolved"
  return "pending"
}

function mapTaskToFaultRecord(t: WorkbenchOverview["recent_tasks"][0]): FaultRecord {
  const status = normalizeFaultStatus(t.status || "")
  const level = (t.maintenance_level || "").toLowerCase()
  const severity: FaultRecord["severity"] =
    level === "emergency" ? "critical" : level === "standard" ? "warning" : "info"
  return {
    id: String(t.id),
    deviceName: t.title || t.equipment_type,
    deviceCode: t.asset_code || t.work_order_id || `TASK-${t.id}`,
    faultType: t.maintenance_level || "检修",
    severity,
    status,
    time: t.updated_at ? String(t.updated_at).replace("T", " ").slice(0, 16) : "--",
  }
}

export default function DashboardPage() {
  const router = useRouter()
  const [viewState, setViewState] = useState<"normal" | "loading" | "empty" | "error">("normal")
  const [activeTab, setActiveTab] = useState("all")
  const [overview, setOverview] = useState<WorkbenchOverview | null>(null)
  const [runtimeSnapshot, setRuntimeSnapshot] = useState<RuntimeSnapshot | null>(null)
  const [healthStatus, setHealthStatus] = useState<{ status: string; database: string } | null>(null)
  const [linkedTaskDetails, setLinkedTaskDetails] = useState<Array<Awaited<ReturnType<typeof fetchTaskDetail>>>>([])
  const [linkedWorkOrderTotal, setLinkedWorkOrderTotal] = useState(0)
  const [linkedPendingCaseTotal, setLinkedPendingCaseTotal] = useState(0)
  const [linkedCaseTotal, setLinkedCaseTotal] = useState(0)

  /** 故障记录表：关键词 + 严重程度（在 Tab 状态筛选之上叠加） */
  const [faultFilterKeyword, setFaultFilterKeyword] = useState("")
  const [faultFilterSeverity, setFaultFilterSeverity] = useState<
    "all" | FaultRecord["severity"]
  >("all")
  const [removedFaultIds, setRemovedFaultIds] = useState<string[]>([])
  const [pendingDeleteRecord, setPendingDeleteRecord] = useState<FaultRecord | null>(null)

  const loadOverview = useCallback(async () => {
    setViewState("loading")
    try {
      const [o, metrics, health] = await Promise.all([
        fetchWorkbenchOverview(),
        fetchSystemMetrics(),
        fetchHealth(),
      ])
      setOverview(o)
      setRuntimeSnapshot(metrics as RuntimeSnapshot)
      setHealthStatus(health)
      const maintenanceToken = getMaintenanceToken()
      const [historyResult, workOrderResult, caseResult] = await Promise.allSettled([
        fetchMaintenanceHistory({ limit: 12 }),
        maintenanceToken ? listWorkOrders(maintenanceToken, 1) : Promise.resolve(null),
        fetchCasesList({ limit: 50 }),
      ])

      const historyTasks =
        historyResult.status === "fulfilled" ? historyResult.value.tasks ?? [] : []
      const detailResults = await Promise.allSettled(
        historyTasks.slice(0, 8).map((task: { id: number }) => fetchTaskDetail(task.id)),
      )
      setLinkedTaskDetails(
        detailResults
          .filter(
            (
              item,
            ): item is PromiseFulfilledResult<Awaited<ReturnType<typeof fetchTaskDetail>>> =>
              item.status === "fulfilled",
          )
          .map((item: PromiseFulfilledResult<Awaited<ReturnType<typeof fetchTaskDetail>>>) => item.value),
      )
      setLinkedWorkOrderTotal(
        workOrderResult.status === "fulfilled" ? Number(workOrderResult.value?.total ?? 0) : 0,
      )
      if (caseResult.status === "fulfilled") {
        const cases = caseResult.value.cases ?? []
        setLinkedCaseTotal(Number(caseResult.value.total ?? cases.length))
        setLinkedPendingCaseTotal(
          cases.filter((item: { status: string }) => item.status === "pending_review").length,
        )
      } else {
        setLinkedCaseTotal(0)
        setLinkedPendingCaseTotal(0)
      }
      const hasNonZeroStats = Array.isArray(o.stats)
        ? o.stats.some((s) => Number(s?.value ?? 0) > 0)
        : false
      const hasRecentItems =
        (Array.isArray(o.recent_tasks) && o.recent_tasks.length > 0) ||
        (Array.isArray(o.recent_cases) && o.recent_cases.length > 0)
      setViewState(hasNonZeroStats || hasRecentItems ? "normal" : "empty")
    } catch {
      setViewState("error")
    }
  }, [])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  useEffect(() => {
    const handleModeChanged = () => {
      void loadOverview()
    }
    window.addEventListener(DEMO_MODE_CHANGED_EVENT, handleModeChanged as EventListener)
    return () => {
      window.removeEventListener(DEMO_MODE_CHANGED_EVENT, handleModeChanged as EventListener)
    }
  }, [loadOverview])

  const handleRefresh = () => {
    void loadOverview()
  }

  const faultFromApi = useMemo(() => {
    if (!overview?.recent_tasks?.length) return []
    return overview.recent_tasks.map(mapTaskToFaultRecord)
  }, [overview])

  const timelineData = useMemo(() => {
    if (!overview?.recent_cases?.length) return []
    return overview.recent_cases.map((c) => ({
      id: String(c.id),
      type: "fault" as const,
      title: c.title,
      description: `${c.equipment_type} · ${c.status}`,
      time: formatDateTimeLocal(c.updated_at),
    }))
  }, [overview])

  const dashboardKpi = useMemo(() => {
    const recentTasks = overview?.recent_tasks ?? []
    const taskTotal = recentTasks.length
    const unresolved = recentTasks.filter((t) => {
      return normalizeFaultStatus(String(t.status || "")) !== "resolved"
    }).length
    const faultRate = taskTotal > 0 ? (unresolved / taskTotal) * 100 : 0
    const faultTrend = recentTasks.length
      ? recentTasks.map((t) => {
          return normalizeFaultStatus(String(t.status || "")) === "resolved" ? 0 : 100
        })
      : [0]

    const durations = (runtimeSnapshot?.durations ?? []).filter(
      (d) => d?.name === "http_request_duration_ms" && Number(d.count ?? 0) > 0,
    )
    const weightedMsSum = durations.reduce(
      (sum, d) => sum + Number(d.avg_ms ?? 0) * Number(d.count ?? 0),
      0,
    )
    const weightedCount = durations.reduce((sum, d) => sum + Number(d.count ?? 0), 0)
    const avgLatencyMs = weightedCount > 0 ? weightedMsSum / weightedCount : 0
    const latencySeries = durations.length
      ? durations.map((d) => Number(d.avg_ms ?? 0)).slice(0, 12)
      : [0]

    const counters = runtimeSnapshot?.counters ?? []
    const totalReq = counters
      .filter((c) => c?.name === "http_requests_total")
      .reduce((sum, c) => sum + Number(c.value ?? 0), 0)
    const successReq = counters
      .filter((c) => {
        if (c?.name !== "http_requests_total") return false
        const statusCode = Number(c.labels?.status_code ?? 0)
        return statusCode >= 200 && statusCode < 400
      })
      .reduce((sum, c) => sum + Number(c.value ?? 0), 0)
    const requestSuccessRate = totalReq > 0 ? (successReq / totalReq) * 100 : 0
    const throughputSeriesRaw = counters
      .filter((c) => c?.name === "http_requests_total")
      .map((c) => Number(c.value ?? 0))
      .slice(0, 12)
    const throughputSeries = throughputSeriesRaw.length ? throughputSeriesRaw : [0]

    const healthScore =
      healthStatus?.status === "healthy" && healthStatus?.database === "connected"
        ? 100
        : healthStatus
          ? 60
          : 0

    return {
      faultRate,
      faultTrend,
      avgLatencyMs,
      latencySeries,
      requestSuccessRate,
      throughputSeries,
      healthScore,
      hasRuntime: totalReq > 0 || weightedCount > 0 || taskTotal > 0,
    }
  }, [overview, runtimeSnapshot, healthStatus])

  const overviewStats = useMemo(() => {
    const m = new Map<string, number>()
    for (const s of overview?.stats ?? []) {
      m.set(String(s.key), Number(s.value ?? 0))
    }
    return {
      knowledgeDocuments: m.get("knowledge_documents") ?? 0,
      knowledgeChunks: m.get("knowledge_chunks") ?? 0,
      activeTasks: m.get("active_tasks") ?? 0,
      pendingCases: m.get("pending_cases") ?? 0,
    }
  }, [overview])

  const unresolvedFaults = useMemo(
    () => faultFromApi.filter((r) => normalizeFaultStatus(String(r.status)) !== "resolved"),
    [faultFromApi],
  )

  const recommendedKnowledge = useMemo(() => {
    const deduped = new Map<
      string,
      { k: string; title: string; desc: string; href: string }
    >()
    linkedTaskDetails.forEach((task) => {
      ;(task.source_refs ?? []).forEach((ref: NonNullable<typeof task.source_refs>[number]) => {
        const key = String(ref.chunk_id ?? `${task.id}-${ref.title}`)
        if (deduped.has(key)) return
        deduped.set(key, {
          k: key,
          title: ref.title || "无",
          desc:
            ref.section_path ||
            ref.section_reference ||
            ref.page_reference ||
            `来自任务 #${task.id} 的已引用知识片段`,
          href: `/tasks/${task.id}`,
        })
      })
    })
    return Array.from(deduped.values()).slice(0, 4)
  }, [linkedTaskDetails])

  const linkedKnowledgeCount = useMemo(
    () =>
      linkedTaskDetails.reduce((sum, task) => {
        return sum + (task.source_refs?.length ?? 0)
      }, 0),
    [linkedTaskDetails],
  )

  const closedLoopSteps = useMemo(
    () => [
      {
        title: "告警触发",
        desc: `待处理 ${unresolvedFaults.length} 条`,
        state: unresolvedFaults.length > 0 ? "active" : "done",
      },
      {
        title: "AI诊断",
        desc: `进行中 ${overviewStats.activeTasks} 条`,
        state: overviewStats.activeTasks > 0 ? "active" : "pending",
      },
      {
        title: "推荐知识",
        desc:
          linkedKnowledgeCount > 0
            ? `已关联 ${linkedKnowledgeCount} 条知识引用`
            : "暂无已落库知识引用",
        state: linkedKnowledgeCount > 0 ? "active" : "pending",
      },
      {
        title: "生成工单",
        desc: linkedWorkOrderTotal > 0 ? `已生成 ${linkedWorkOrderTotal} 条` : "暂无已生成工单",
        state: linkedWorkOrderTotal > 0 ? "active" : "pending",
      },
      {
        title: "案例沉淀",
        desc:
          linkedPendingCaseTotal > 0
            ? `待审核 ${linkedPendingCaseTotal} 条`
            : linkedCaseTotal > 0
              ? `已沉淀 ${linkedCaseTotal} 条`
              : "暂无沉淀案例",
        state:
          linkedPendingCaseTotal > 0
            ? "active"
            : linkedCaseTotal > 0
              ? "done"
              : "pending",
      },
    ],
    [
      linkedCaseTotal,
      linkedKnowledgeCount,
      linkedPendingCaseTotal,
      linkedWorkOrderTotal,
      overviewStats.activeTasks,
      unresolvedFaults.length,
    ],
  )

  const faultFiltersActive =
    faultFilterKeyword.trim().length > 0 || faultFilterSeverity !== "all"

  const filteredFault = useMemo(() => {
    let base = faultFromApi.filter((r) => !removedFaultIds.includes(r.id))
    if (activeTab !== "all") {
      base = base.filter((r) => {
        if (activeTab === "pending") return r.status === "pending"
        if (activeTab === "processing") return r.status === "processing"
        if (activeTab === "resolved") return r.status === "resolved"
        return true
      })
    }
    if (faultFilterSeverity !== "all") {
      base = base.filter((r) => r.severity === faultFilterSeverity)
    }
    const q = faultFilterKeyword.trim().toLowerCase()
    if (q) {
      base = base.filter(
        (r) =>
          r.deviceName.toLowerCase().includes(q) ||
          r.deviceCode.toLowerCase().includes(q) ||
          r.faultType.toLowerCase().includes(q) ||
          (r.operator?.toLowerCase().includes(q) ?? false),
      )
    }
    return base
  }, [faultFromApi, activeTab, faultFilterSeverity, faultFilterKeyword, removedFaultIds])

  const resetFaultFilters = () => {
    setFaultFilterKeyword("")
    setFaultFilterSeverity("all")
  }

  const handleFaultMenu = (action: "detail" | "process" | "export" | "delete", record: FaultRecord) => {
    const id = Number(record.id)

    if (action === "detail") {
      if (!Number.isFinite(id)) return
      router.push(`/tasks/${id}`)
      return
    }

    if (action === "process") {
      if (!Number.isFinite(id)) return
      router.push(`/tasks/${id}?action=process`)
      return
    }

    if (action === "delete") {
      setPendingDeleteRecord(record)
      return
    }

    // export
    void (async () => {
      if (!Number.isFinite(id)) {
        downloadJsonInBrowser(`fault-record-${record.id}-demo.json`, {
          exported_at: new Date().toISOString(),
          export_summary:
            "当前为演示故障记录（任务 ID 非数字），无法调用后端导出接口；已导出页面快照。",
          snapshot: record,
        })
        return
      }
      try {
        const payload = await fetchTaskExport(id)
        const stamp = new Date().toISOString().slice(0, 19).replace(/:/g, "-")
        downloadJsonInBrowser(`检修任务-${id}-导出-${stamp}.json`, payload)
      } catch (e) {
        downloadJsonInBrowser(`检修任务-${id}-导出-失败-${Date.now()}.json`, {
          exported_at: new Date().toISOString(),
          export_summary: "后端导出失败，以下为本地快照与错误信息。",
          error: e instanceof Error ? e.message : String(e),
          snapshot: record,
        })
      }
    })()
  }

  const confirmDeleteRecord = () => {
    if (!pendingDeleteRecord) return
    const deletingRecord = pendingDeleteRecord
    const deletingId = Number(deletingRecord.id)
    setPendingDeleteRecord(null)
    void (async () => {
      if (!Number.isFinite(deletingId)) {
        toast.error("记录 ID 非法，无法删除")
        return
      }
      try {
        await deleteMaintenanceTask(deletingId)
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "删除失败，请稍后重试")
        return
      }
      setRemovedFaultIds((prev) =>
        prev.includes(deletingRecord.id) ? prev : [...prev, deletingRecord.id],
      )
      toast.success("记录已删除")
    })()
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="app-main">
        {/* Page Header */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground">检修总览</h1>
            <p className="mt-1 text-sm text-muted-foreground">统一查看设备状态、诊断任务、工单处理与知识沉淀</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="app-btn-secondary h-8 gap-1.5 px-3"
              onClick={handleRefresh}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              刷新
            </button>
          </div>
        </div>

        {/* Error State */}
        {viewState === "error" && (
          <ErrorState
            title="数据加载失败"
            description="无法连接到诊断服务器，请检查网络连接"
            onRetry={() => void loadOverview()}
          />
        )}

        {/* Loading State */}
        {viewState === "loading" && <DashboardSkeleton />}

        {/* Empty State */}
        {viewState === "empty" && (
          <div className="space-y-6">
            {/* Stats - Even empty state shows stats */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                title="设备总数"
                value={0}
                unit="台"
                icon={<Server className="h-4 w-4" />}
              />
              <StatCard
                title="在线设备"
                value={0}
                unit="台"
                icon={<Activity className="h-4 w-4" />}
                status="success"
              />
              <StatCard
                title="故障告警"
                value={0}
                unit="条"
                icon={<AlertCircle className="h-4 w-4" />}
                status="warning"
              />
              <StatCard
                title="今日已处理"
                value={0}
                unit="条"
                icon={<CheckCircle className="h-4 w-4" />}
                status="success"
              />
            </div>

            <EmptyState
              type="no-devices"
              title="暂无监控设备"
              description="当前暂无监控设备与诊断数据，请检查数据接入与后端服务状态。"
            />
          </div>
        )}

        {/* Normal State */}
        {viewState === "normal" && (
          <div className="space-y-6">
            {/* 今日检修概览 */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                title="知识文档"
                value={overviewStats.knowledgeDocuments}
                unit="条"
                icon={<FileCheck className="h-4 w-4" />}
                status="normal"
              />
              <StatCard
                title="知识分段"
                value={overviewStats.knowledgeChunks}
                unit="条"
                icon={<Layers className="h-4 w-4" />}
                status="normal"
              />
              <StatCard
                title="进行中任务"
                value={overviewStats.activeTasks}
                unit="条"
                icon={<Activity className="h-4 w-4" />}
                status="warning"
              />
              <StatCard
                title="待审核案例"
                value={overviewStats.pendingCases}
                unit="条"
                icon={<AlertCircle className="h-4 w-4" />}
                status="critical"
              />
            </div>

            {/* 待处理告警 + 推荐知识 */}
            <div className="grid gap-6 lg:grid-cols-3 transition-all duration-300">
              <section className="app-card lg:col-span-2 overflow-hidden">
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">待处理告警</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      从告警快速进入诊断或生成工单，形成检修闭环
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8"
                    onClick={() => router.push("/tasks")}
                  >
                    查看全部诊断
                  </Button>
                </div>
                <div className="divide-y divide-border">
                  {unresolvedFaults.slice(0, 4).map((r) => (
                      <div key={r.id} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-foreground line-clamp-1">
                              {r.deviceName}
                            </span>
                            <span className="text-xs text-muted-foreground font-mono">{r.deviceCode}</span>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground line-clamp-1">
                            {r.faultType} · 更新 {r.time}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-8"
                            onClick={() => {
                              const id = Number(r.id)
                              if (!Number.isFinite(id)) return
                              router.push(`/tasks/${id}`)
                            }}
                          >
                            查看详情
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            className="h-8"
                            onClick={() => {
                              const id = Number(r.id)
                              if (!Number.isFinite(id)) return
                              router.push(`/tasks/${id}?action=process`)
                            }}
                          >
                            开始诊断
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-8"
                            onClick={() => {
                              const id = Number(r.id)
                              if (!Number.isFinite(id)) return
                              router.push(`/tasks/${id}`)
                            }}
                          >
                            生成工单
                          </Button>
                        </div>
                      </div>
                    ))}
                  {unresolvedFaults.length === 0 ? (
                    <div className="px-5 py-10 text-center text-sm text-muted-foreground">暂无待处理告警</div>
                  ) : null}
                </div>
              </section>

              <section className="app-card overflow-hidden">
                <div className="border-b border-border px-5 py-4">
                  <h3 className="text-sm font-semibold text-foreground">推荐知识</h3>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    手册 / 案例 / SOP / 专家经验
                  </p>
                </div>
                <div className="p-5 space-y-3">
                  {recommendedKnowledge.map((it) => (
                    <button
                      key={it.k}
                      type="button"
                      className="w-full rounded-lg border border-border bg-background p-3 text-left hover:bg-accent transition-colors"
                      onClick={() => router.push(it.href)}
                    >
                      <div className="text-sm font-medium text-foreground">{it.title}</div>
                      <div className="mt-1 text-xs text-muted-foreground line-clamp-2">{it.desc}</div>
                    </button>
                  ))}
                  {recommendedKnowledge.length === 0 ? (
                    <div className="rounded-lg border border-border bg-background p-3 text-xs text-muted-foreground">
                      暂无推荐知识
                    </div>
                  ) : null}
                </div>
              </section>
            </div>

            {/* 检修闭环状态 */}
            <section className="app-card p-5 transition-all duration-300">
              <h3 className="text-base font-semibold text-foreground">检修闭环状态</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                告警触发 → AI诊断 → 推荐知识 → 生成工单 → 案例沉淀
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-5">
                {closedLoopSteps.map((step, idx) => (
                  <div key={step.title} className="relative rounded-xl border border-border bg-background p-3">
                    {idx < 4 ? (
                      <div className="absolute -right-2 top-1/2 hidden h-0.5 w-4 -translate-y-1/2 bg-border sm:block" />
                    ) : null}
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium text-foreground">{step.title}</div>
                      <span
                        className={`inline-flex h-2.5 w-2.5 rounded-full ${
                          step.state === "done"
                            ? "bg-emerald-400"
                            : step.state === "active"
                              ? "bg-blue-400"
                              : "bg-amber-400"
                        }`}
                      />
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{step.desc}</div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={() => router.push("/tasks")}>
                  继续诊断
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => router.push("/tickets")}>
                  查看工单
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => router.push("/cases")}>
                  查看案例沉淀
                </Button>
              </div>
            </section>
          </div>
        )}
      </main>

      <AlertDialog
        open={Boolean(pendingDeleteRecord)}
        onOpenChange={(open) => {
          if (!open) setPendingDeleteRecord(null)
        }}
      >
        <AlertDialogContent className="border-border bg-background text-foreground">
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除记录</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              {pendingDeleteRecord
                ? `确认删除记录「${pendingDeleteRecord.deviceName}」？删除后将从当前列表中移除。`
                : "确认删除该条记录？"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-border bg-transparent text-foreground hover:bg-muted hover:text-foreground">
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-500 text-white hover:bg-red-500/90"
              onClick={confirmDeleteRecord}
            >
              确定删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

