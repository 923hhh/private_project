"use client"

import { use, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Check,
  CheckCircle2,
  Copy,
  Edit3,
  ExternalLink,
  FileText,
  Link2,
  Share2,
  Tag,
  Wrench,
  XCircle,
} from "lucide-react"
import { fetchCaseDetail, reviewMaintenanceCase, addCaseCorrection, type MaintenanceCaseDetail } from "@/features/cases/api"
import { Header } from "@/shared/components/brand/app-header"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog"
import { formatDateTimeLocal } from "@/shared/lib/utils"

interface PageProps {
  params: Promise<{ caseId: string }>
}

type FaultLevel = "low" | "medium" | "urgent"
type VerifyStatus = "verified" | "pending" | "rejected"

const faultLevelConfig: Record<FaultLevel, { label: string; className: string }> = {
  low: { label: "例行", className: "bg-blue-500/15 text-blue-400 border-blue-500/20" },
  medium: { label: "标准", className: "bg-amber-500/15 text-amber-400 border-amber-500/20" },
  urgent: { label: "紧急", className: "bg-red-500/15 text-red-400 border-red-500/20" },
}

const verifyStatusConfig: Record<VerifyStatus, { label: string; dotColor: string; textColor: string; bgColor: string }> = {
  verified: { label: "已验证", dotColor: "bg-emerald-400", textColor: "text-emerald-400", bgColor: "bg-emerald-500/10" },
  pending: { label: "待验证", dotColor: "bg-amber-400", textColor: "text-amber-400", bgColor: "bg-amber-500/10" },
  rejected: { label: "已驳回", dotColor: "bg-red-400", textColor: "text-red-400", bgColor: "bg-red-500/10" },
}

const tocItems = [
  { id: "symptoms", label: "故障现象" },
  { id: "root-cause", label: "根因分析" },
  { id: "action-plan", label: "处理方案" },
  { id: "evidence", label: "证据数据" },
  { id: "related", label: "关联知识" },
]

function mapPriorityToLevel(priority: string | null | undefined): FaultLevel {
  const normalized = String(priority || "").trim().toLowerCase()
  if (normalized === "urgent" || normalized === "high") return "urgent"
  if (normalized === "low" || normalized === "routine") return "low"
  return "medium"
}

function mapCaseStatus(status: string | null | undefined): VerifyStatus {
  const normalized = String(status || "").trim().toLowerCase()
  if (normalized === "approved") return "verified"
  if (normalized === "rejected") return "rejected"
  return "pending"
}

function textOrNone(value: string | null | undefined) {
  const normalized = String(value || "").trim()
  return normalized || "无"
}

function splitLines(value: string | null | undefined) {
  return String(value || "")
    .split(/\r?\n+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function SectionEmpty() {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
      无
    </div>
  )
}

export default function CaseDetailPage({ params }: PageProps) {
  const { caseId } = use(params)
  const [activeSection, setActiveSection] = useState("symptoms")
  const [copiedSteps, setCopiedSteps] = useState(false)
  const [remoteCase, setRemoteCase] = useState<MaintenanceCaseDetail | null>(null)
  const [reviewBusy, setReviewBusy] = useState(false)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectNote, setRejectNote] = useState("")
  const [correctionOpen, setCorrectionOpen] = useState(false)
  const [correctionTarget, setCorrectionTarget] = useState("")
  const [correctionOriginal, setCorrectionOriginal] = useState("")
  const [correctionContent, setCorrectionContent] = useState("")
  const [correctionNote, setCorrectionNote] = useState("")

  const numericCaseId = useMemo(() => {
    const match = caseId.match(/(\d+)/)
    return match ? Number(match[1]) : NaN
  }, [caseId])

  useEffect(() => {
    if (!Number.isFinite(numericCaseId)) return
    void (async () => {
      try {
        const detail = await fetchCaseDetail(numericCaseId)
        setRemoteCase(detail)
      } catch {
        toast.error("案例详情加载失败")
      }
    })()
  }, [numericCaseId])

  const levelConfig = faultLevelConfig[mapPriorityToLevel(remoteCase?.priority)]
  const statusConfig = verifyStatusConfig[mapCaseStatus(remoteCase?.status)]

  const summaryText = textOrNone(remoteCase?.symptom_description)
  const rootCauseLines = splitLines(remoteCase?.resolution_summary)
  const processingSteps = (remoteCase?.processing_steps || []).filter((item) => item.trim())
  const knowledgeRefs = remoteCase?.knowledge_refs || []
  const correctionRecords = remoteCase?.corrections || []

  useEffect(() => {
    const handleScroll = () => {
      const sections = tocItems.map((item) => document.getElementById(item.id))
      const scrollPosition = window.scrollY + 100
      for (let index = sections.length - 1; index >= 0; index -= 1) {
        const section = sections[index]
        if (section && section.offsetTop <= scrollPosition) {
          setActiveSection(tocItems[index].id)
          break
        }
      }
    }

    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  const handleApprove = async () => {
    if (!Number.isFinite(numericCaseId)) return
    setReviewBusy(true)
    try {
      const updated = await reviewMaintenanceCase(numericCaseId, { action: "approve", reviewer_name: "评审专家" })
      setRemoteCase(updated)
      toast.success("案例已通过审核，已沉淀为知识文档")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "审核失败")
    } finally {
      setReviewBusy(false)
    }
  }

  const handleReject = async () => {
    if (!Number.isFinite(numericCaseId)) return
    setReviewBusy(true)
    try {
      const updated = await reviewMaintenanceCase(numericCaseId, {
        action: "reject",
        reviewer_name: "评审专家",
        review_note: rejectNote,
      })
      setRemoteCase(updated)
      setRejectOpen(false)
      setRejectNote("")
      toast.success("案例已驳回")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "驳回失败")
    } finally {
      setReviewBusy(false)
    }
  }

  const openCorrection = (target: string, original: string) => {
    setCorrectionTarget(target)
    setCorrectionOriginal(original || "无")
    setCorrectionContent("")
    setCorrectionNote("")
    setCorrectionOpen(true)
  }

  const submitCorrection = async () => {
    if (!Number.isFinite(numericCaseId) || !correctionContent.trim()) return
    try {
      const updated = await addCaseCorrection(numericCaseId, {
        correction_target: correctionTarget,
        original_content: correctionOriginal === "无" ? "" : correctionOriginal,
        corrected_content: correctionContent,
        note: correctionNote || undefined,
      })
      setRemoteCase(updated)
      setCorrectionOpen(false)
      toast.success("修正已提交")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "提交失败")
    }
  }

  const copyActionSteps = () => {
    void (async () => {
      const text = processingSteps.length > 0
        ? processingSteps.map((item, index) => `${index + 1}. ${item}`).join("\n")
        : "无"
      await navigator.clipboard.writeText(text)
      toast.success("处理步骤已复制")
      setCopiedSteps(true)
      setTimeout(() => setCopiedSteps(false), 2000)
    })()
  }

  const shareCase = () => {
    void (async () => {
      const shareUrl = typeof window !== "undefined" ? window.location.href : ""
      if (!shareUrl) return
      try {
        if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
          await navigator.share({
            title: remoteCase?.title || caseId,
            text: `查看故障案例：${remoteCase?.title || caseId}`,
            url: shareUrl,
          })
          toast.success("已打开系统分享面板")
          return
        }
        await navigator.clipboard.writeText(shareUrl)
        toast.success("复制链接成功")
      } catch {
        toast.error("分享失败，请稍后重试")
      }
    })()
  }

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id)
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="app-main app-main-wide">
        <section className="app-page-head">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-4">
              <Link
                href="/cases"
                className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="hidden sm:inline">返回案例库</span>
              </Link>
              <span className="text-muted-foreground">/</span>
              <span className="text-sm text-foreground/85">{caseId}</span>
            </div>
            <div className="flex items-center gap-2">
              <button className="app-btn-secondary px-3 py-1.5" onClick={shareCase}>
                <Share2 className="w-4 h-4" />
                <span className="hidden sm:inline">分享</span>
              </button>
              {mapCaseStatus(remoteCase?.status) === "pending" ? (
                <>
                  <button
                    className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
                    onClick={handleApprove}
                    disabled={reviewBusy}
                  >
                    <Check className="w-4 h-4" />
                    通过审核
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-red-500/30 px-3 py-1.5 text-sm text-red-400 transition-colors hover:bg-red-500/10 disabled:opacity-50"
                    onClick={() => setRejectOpen(true)}
                    disabled={reviewBusy}
                  >
                    驳回
                  </button>
                </>
              ) : mapCaseStatus(remoteCase?.status) === "verified" ? (
                <span className="inline-flex items-center gap-2 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                  已通过审核
                </span>
              ) : (
                <span className="inline-flex items-center gap-2 rounded-md border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-sm text-red-400">
                  <XCircle className="w-4 h-4" />
                  已驳回
                </span>
              )}
            </div>
          </div>
        </section>

        <div className="flex gap-6">
          <aside className="hidden w-48 flex-shrink-0 lg:block">
            <div className="sticky top-20">
              <div className="max-h-[calc(100vh-8rem)] min-h-0 overflow-y-auto overscroll-y-contain pr-3 pb-6">
                <nav className="space-y-1">
                  <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">目录</p>
                  {tocItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => scrollToSection(item.id)}
                      className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                        activeSection === item.id
                          ? "border-l-2 border-[#5e6ad2] bg-muted text-foreground"
                          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </nav>
              </div>
            </div>
          </aside>

          <main className="min-w-0 flex-1">
            <div className="app-card mb-6 p-6">
              <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex-1">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${levelConfig.className}`}>
                      {levelConfig.label}
                    </span>
                    <div className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 ${statusConfig.bgColor}`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${statusConfig.dotColor}`} />
                      <span className={`text-xs ${statusConfig.textColor}`}>{statusConfig.label}</span>
                    </div>
                    {(remoteCase?.fault_type ? [remoteCase.fault_type] : []).map((tag) => (
                      <span key={tag} className="app-badge text-foreground/85">{tag}</span>
                    ))}
                  </div>
                  <h1 className="mb-2 text-xl font-semibold text-foreground sm:text-2xl">
                    {textOrNone(remoteCase?.title)}
                  </h1>
                  <p className="text-sm leading-relaxed text-muted-foreground">{summaryText}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-3 lg:grid-cols-6">
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">设备名称</p>
                  <p className="text-sm text-foreground/85">{textOrNone(remoteCase?.equipment_type)}</p>
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">设备型号</p>
                  <p className="font-mono text-sm text-foreground/85">{textOrNone(remoteCase?.equipment_model)}</p>
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">故障等级</p>
                  <p className="text-sm text-foreground/85">{levelConfig.label}</p>
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">更新时间</p>
                  <p className="text-sm text-foreground/85">{textOrNone(formatDateTimeLocal(remoteCase?.updated_at || null))}</p>
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">负责人</p>
                  <p className="text-sm text-foreground/85">无</p>
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted-foreground">审核人</p>
                  <p className="text-sm text-foreground/85">{textOrNone(remoteCase?.reviewer_name)}</p>
                </div>
              </div>
            </div>

            <section id="symptoms" className="app-card mb-6 scroll-mt-20 p-6">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                故障现象
                <button
                  className="ml-auto flex items-center gap-1 text-xs text-[#5e6ad2] transition-colors hover:text-[#7170ff]"
                  onClick={() => openCorrection("model_output", remoteCase?.symptom_description || "")}
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  修正
                </button>
              </h2>
              <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-red-400" />
                  <h3 className="text-sm font-medium text-red-400">故障描述</h3>
                </div>
                <p className="text-sm leading-relaxed text-foreground/85">{summaryText}</p>
              </div>
            </section>

            <section id="root-cause" className="app-card mb-6 scroll-mt-20 p-6">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
                <FileText className="w-5 h-5 text-emerald-400" />
                根因分析
                <button
                  className="ml-auto flex items-center gap-1 text-xs text-[#5e6ad2] transition-colors hover:text-[#7170ff]"
                  onClick={() => openCorrection("summary", remoteCase?.resolution_summary || "")}
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  修正
                </button>
              </h2>
              {rootCauseLines.length > 0 ? (
                <div className="space-y-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
                  <h3 className="text-sm font-medium text-emerald-400">诊断结论</h3>
                  {rootCauseLines.map((line, index) => (
                    <p key={`${line}-${index}`} className="text-sm leading-7 text-foreground">{line}</p>
                  ))}
                </div>
              ) : (
                <SectionEmpty />
              )}
            </section>

            <section id="action-plan" className="app-card mb-6 scroll-mt-20 p-6">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
                  <Wrench className="w-5 h-5 text-blue-400" />
                  处理方案
                  <button
                    className="ml-2 flex items-center gap-1 text-xs text-[#5e6ad2] transition-colors hover:text-[#7170ff]"
                    onClick={() => openCorrection("procedure", processingSteps.join("\n"))}
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    修正
                  </button>
                </h2>
                <button onClick={copyActionSteps} className="app-btn-secondary px-3 py-1.5">
                  {copiedSteps ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-400" />
                      已复制
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      复制处理步骤
                    </>
                  )}
                </button>
              </div>

              {processingSteps.length > 0 ? (
                <div className="overflow-hidden rounded-lg border border-border bg-muted/20">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase text-muted-foreground">步骤</th>
                        <th className="px-4 py-3 text-left text-xs font-medium uppercase text-muted-foreground">操作内容</th>
                        <th className="hidden px-4 py-3 text-left text-xs font-medium uppercase text-muted-foreground sm:table-cell">负责人</th>
                        <th className="hidden px-4 py-3 text-left text-xs font-medium uppercase text-muted-foreground sm:table-cell">预计时长</th>
                      </tr>
                    </thead>
                    <tbody>
                      {processingSteps.map((item, index) => (
                        <tr key={`${item}-${index}`} className="border-b border-border last:border-0">
                          <td className="px-4 py-3">
                            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#5e6ad2]/20 text-xs font-medium text-[#5e6ad2]">
                              {index + 1}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-foreground/85">{item}</td>
                          <td className="hidden px-4 py-3 text-sm text-muted-foreground sm:table-cell">无</td>
                          <td className="hidden px-4 py-3 text-sm font-mono text-muted-foreground sm:table-cell">无</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <SectionEmpty />
              )}
            </section>

            <section id="evidence" className="app-card mb-6 scroll-mt-20 p-6">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
                <Activity className="w-5 h-5 text-[#5e6ad2]" />
                证据数据
              </h2>
              <SectionEmpty />
            </section>

            <section id="related" className="app-card scroll-mt-20 p-6">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
                <Link2 className="w-5 h-5 text-muted-foreground" />
                关联知识
              </h2>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <div>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground/85">
                    <BookOpen className="w-4 h-4 text-muted-foreground" />
                    关联文档
                  </h3>
                  <div className="space-y-2">
                    {knowledgeRefs.length > 0 ? (
                      knowledgeRefs.map((doc, index) => {
                        const href = doc.document_id ? `/knowledge/${doc.document_id}` : "#"
                        const title = doc.title || doc.source_name || "无"
                        return doc.document_id ? (
                          <Link
                            key={`${doc.document_id}-${index}`}
                            href={href}
                            className="group flex items-center justify-between rounded-lg border border-border bg-muted/20 p-3 transition-colors hover:bg-muted/40"
                          >
                            <span className="text-sm text-foreground/85 group-hover:text-foreground">{title}</span>
                            <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-[#5e6ad2]" />
                          </Link>
                        ) : (
                          <div
                            key={`${title}-${index}`}
                            className="flex items-center justify-between rounded-lg border border-border bg-muted/20 p-3"
                          >
                            <span className="text-sm text-foreground/85">{title}</span>
                            <span className="text-xs text-muted-foreground">无链接</span>
                          </div>
                        )
                      })
                    ) : (
                      <SectionEmpty />
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground/85">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    修正记录
                  </h3>
                  <div className="space-y-2">
                    {correctionRecords.length > 0 ? (
                      correctionRecords.map((item) => (
                        <div key={item.id} className="rounded-lg border border-border bg-muted/20 p-3">
                          <div className="mb-1 text-xs text-muted-foreground">{item.correction_target}</div>
                          <div className="text-sm text-foreground">{textOrNone(item.corrected_content)}</div>
                          <div className="mt-2 text-xs text-muted-foreground">
                            {textOrNone(formatDateTimeLocal(item.created_at))}
                          </div>
                        </div>
                      ))
                    ) : (
                      <SectionEmpty />
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground/85">
                    <Tag className="w-4 h-4 text-muted-foreground" />
                    案例附加信息
                  </h3>
                  <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-4 text-sm">
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-muted-foreground">故障类型</span>
                      <span className="text-right text-foreground">{textOrNone(remoteCase?.fault_type)}</span>
                    </div>
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-muted-foreground">报修来源</span>
                      <span className="text-right text-foreground">{textOrNone(remoteCase?.report_source)}</span>
                    </div>
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-muted-foreground">工单编号</span>
                      <span className="text-right text-foreground">{textOrNone(remoteCase?.work_order_id)}</span>
                    </div>
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-muted-foreground">审核时间</span>
                      <span className="text-right text-foreground">{textOrNone(formatDateTimeLocal(remoteCase?.reviewed_at || null))}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </main>
        </div>
      </div>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent className="max-w-md border-border bg-popover text-popover-foreground">
          <DialogHeader>
            <DialogTitle>驳回案例</DialogTitle>
          </DialogHeader>
          <textarea
            className="h-24 w-full resize-none rounded-lg border border-input bg-background p-3 text-sm text-foreground placeholder:text-muted-foreground"
            placeholder="请填写驳回理由..."
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
          />
          <div className="mt-4 flex justify-end gap-3">
            <button className="px-4 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground" onClick={() => setRejectOpen(false)}>取消</button>
            <button className="rounded-md bg-red-600 px-4 py-2 text-sm text-white transition-colors hover:bg-red-500 disabled:opacity-50" onClick={handleReject} disabled={reviewBusy}>确认驳回</button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={correctionOpen} onOpenChange={setCorrectionOpen}>
        <DialogContent className="max-w-lg border-border bg-popover text-popover-foreground">
          <DialogHeader>
            <DialogTitle>修正内容</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">原始内容</label>
              <textarea className="h-20 w-full resize-none rounded-lg border border-input bg-muted/35 p-3 text-sm text-muted-foreground" readOnly value={correctionOriginal} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">修正后内容</label>
              <textarea className="h-20 w-full resize-none rounded-lg border border-input bg-background p-3 text-sm text-foreground placeholder:text-muted-foreground" placeholder="请输入修正后的内容..." value={correctionContent} onChange={(e) => setCorrectionContent(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">备注（可选）</label>
              <input className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground" placeholder="修正原因..." value={correctionNote} onChange={(e) => setCorrectionNote(e.target.value)} />
            </div>
          </div>
          <div className="mt-4 flex justify-end gap-3">
            <button className="px-4 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground" onClick={() => setCorrectionOpen(false)}>取消</button>
            <button className="rounded-md bg-[#5e6ad2] px-4 py-2 text-sm text-white transition-colors hover:bg-[#7170ff] disabled:opacity-50" onClick={submitCorrection} disabled={!correctionContent.trim()}>提交修正</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
