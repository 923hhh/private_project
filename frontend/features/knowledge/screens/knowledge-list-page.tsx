"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { fetchKnowledgeDocuments, fetchKnowledgeImports, deleteKnowledgeDocument, deleteKnowledgeImportJob } from "@/features/knowledge/api"
import { toast } from "sonner"
import {
  Search,
  Filter,
  ChevronRight,
  ChevronDown,
  FileText,
  FolderOpen,
  AlertTriangle,
  BookOpen,
  Shield,
  Clock,
  User,
  Edit3,
  Eye,
  Lock,
  ArrowUpDown,
  MoreHorizontal,
  Trash2,
  Copy,
  Star,
  ArrowLeft,
  FolderTree,
  Settings,
  ExternalLink,
  RefreshCw,
} from "lucide-react"
import { Header } from "@/shared/components/brand/app-header"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu"
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

function splitDateTime(value: string) {
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed)) {
    return { date: value || "--", time: "" }
  }
  const date = new Date(parsed)
  return {
    date: new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(date),
    time: new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date),
  }
}

// Types
interface KnowledgeCategory {
  id: string
  name: string
  icon: React.ReactNode
  count: number
  children?: KnowledgeCategory[]
}

interface KnowledgeDocument {
  id: string
  title: string
  categoryId: string
  tags: string[]
  updatedAt: string
  author: string
  status: "draft" | "published"
  permission: "readonly" | "editable"
  abstract: string
  revisions: {
    version: string
    date: string
    author: string
    summary: string
  }[]
  isImportJob?: boolean
  importJobId?: number
  importStatus?: string
  errorMessage?: string
}

// Category Tree Component
function CategoryTree({
  categories,
  selectedCategory,
  onSelect,
  expandedIds,
  onToggle,
}: {
  categories: KnowledgeCategory[]
  selectedCategory: string | null
  onSelect: (id: string) => void
  expandedIds: string[]
  onToggle: (id: string) => void
}) {
  return (
    <ul className="space-y-1">
      {categories.map((category) => {
        const isExpanded = expandedIds.includes(category.id)
        const hasChildren = category.children && category.children.length > 0
        const isSelected = selectedCategory === category.id

        return (
          <li key={category.id}>
            <div
              className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150
                ${isSelected ? "bg-primary/10 text-primary" : "text-foreground hover:bg-muted"}`}
              onClick={() => {
                if (hasChildren) onToggle(category.id)
                onSelect(category.id)
              }}
            >
              {hasChildren ? (
                <button
                  type="button"
                  className="rounded p-0.5 hover:bg-muted"
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggle(category.id)
                  }}
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </button>
              ) : (
                <span className="w-4" />
              )}
              <span className={isSelected ? "text-primary" : "text-muted-foreground"}>{category.icon}</span>
              <span className="flex-1 text-sm font-medium truncate">{category.name}</span>
              <span className="app-chip-muted">{category.count}</span>
            </div>
            {hasChildren && isExpanded && (
              <div className="ml-4 mt-1 border-l border-border pl-2">
                <CategoryTree
                  categories={category.children!}
                  selectedCategory={selectedCategory}
                  onSelect={onSelect}
                  expandedIds={expandedIds}
                  onToggle={onToggle}
                />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

// Document List Item
function DocumentListItem({
  doc,
  isSelected,
  onClick,
  onOpenDetail,
}: {
  doc: KnowledgeDocument
  isSelected: boolean
  onClick: () => void
  onOpenDetail: () => void
}) {
  const statusLabel = doc.isImportJob
    ? doc.importStatus === "failed"
      ? "解析失败"
      : "导入中"
    : doc.status === "published"
      ? "已发布"
      : "草稿"

  const statusClassName = doc.isImportJob
    ? doc.importStatus === "failed"
      ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
      : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
    : doc.status === "published"
      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
      : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
  const updatedAtParts = splitDateTime(doc.updatedAt)

  return (
    <button
      type="button"
      className={`cursor-pointer border-b border-border p-4 transition-all duration-150
        ${isSelected ? "border-l-2 border-l-primary bg-primary/5" : "border-l-2 border-l-transparent hover:bg-muted/60"} w-full text-left`}
      onClick={() => {
        if (isSelected) {
          onOpenDetail()
          return
        }
        onClick()
      }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className={`text-sm font-medium leading-tight ${isSelected ? "text-foreground" : "text-foreground"}`}>
          {doc.title}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          {doc.permission === "readonly" ? (
            <Lock className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <Edit3 className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${statusClassName}`}
          >
            {statusLabel}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {doc.tags.map((tag) => (
          <span key={tag} className="app-chip-muted">
            {tag}
          </span>
        ))}
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <User className="w-3 h-3" />
          {doc.author}
        </span>
        <span className="flex items-start gap-1">
          <Clock className="w-3 h-3" />
          <span className="flex flex-col leading-4">
            <span>{updatedAtParts.date}</span>
            {updatedAtParts.time ? <span>{updatedAtParts.time}</span> : null}
          </span>
        </span>
      </div>
    </button>
  )
}

// Document List Skeleton
function DocumentListSkeleton() {
  return (
    <div className="animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="border-b border-border p-4">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="app-skeleton h-4 w-3/4" />
            <div className="app-skeleton h-5 w-14 rounded-full" />
          </div>
          <div className="flex gap-1.5 mb-2">
            <div className="app-skeleton h-5 w-12 rounded-full" />
            <div className="app-skeleton h-5 w-14 rounded-full" />
            <div className="app-skeleton h-5 w-10 rounded-full" />
          </div>
          <div className="flex gap-3">
            <div className="app-skeleton h-3 w-16" />
            <div className="app-skeleton h-3 w-24" />
          </div>
        </div>
      ))}
    </div>
  )
}

// Empty State - No Document Selected
function EmptyPreview() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-8">
      <div className="app-empty-icon mb-4 h-16 w-16">
        <FileText className="h-8 w-8" />
      </div>
      <h3 className="mb-2 font-medium text-foreground">知识入库流程</h3>
      <div className="space-y-1 text-xs text-muted-foreground">
        <p>① 上传文档</p>
        <p>② 自动解析</p>
        <p>③ 切分知识片段</p>
        <p>④ 向量化索引</p>
        <p>⑤ 审核后入库</p>
      </div>
    </div>
  )
}

export default function KnowledgePageClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const fromCases = searchParams.get("from") === "cases"
  const highlightImportJobId = searchParams.get("highlightImportJob")
  const [selectedCategory, setSelectedCategory] = useState<string | null>("all")
  const [expandedIds, setExpandedIds] = useState<string[]>(["all"])
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [sortBy, setSortBy] = useState<"updated" | "title">("updated")
  const [isLoading, setIsLoading] = useState(false)
  const [showMobilePreview, setShowMobilePreview] = useState(false)
  const [apiDocs, setApiDocs] = useState<KnowledgeDocument[]>([])
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeDocument | null>(null)
  const [importingCount, setImportingCount] = useState(0)
  const [failedImportCount, setFailedImportCount] = useState(0)

  const openDocumentDetail = (doc: KnowledgeDocument) => {
    if (doc.isImportJob) return
    router.push(`/knowledge/${doc.id}`)
  }

  const copyDocumentLink = async (doc: KnowledgeDocument) => {
    const u = `${typeof window !== "undefined" ? window.location.origin : ""}/knowledge/${doc.id}`
    await navigator.clipboard.writeText(u)
    toast.success("链接已复制到剪贴板")
  }

  const handleDeleteDocument = async (doc: KnowledgeDocument) => {
    try {
      if (doc.isImportJob) {
        if (!doc.importJobId) {
          throw new Error("导入任务 ID 缺失，无法删除。")
        }
        await deleteKnowledgeImportJob(doc.importJobId)
      } else {
        await deleteKnowledgeDocument(Number(doc.id))
      }
      setApiDocs((prev) => prev.filter((d) => d.id !== doc.id))
      setSelectedDoc((prev) => (prev?.id === doc.id ? null : prev))
      setDeleteTarget(null)
      toast.success(doc.isImportJob ? "失败记录已删除" : "文档已删除")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败")
    }
  }

  const handleToggle = (id: string) => {
    setExpandedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  const loadKnowledgeState = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setIsLoading(true)
      }
      try {
        const [documentPayload, importPayload] = await Promise.all([
          fetchKnowledgeDocuments(50),
          fetchKnowledgeImports(12),
        ])
        const mappedDocs: KnowledgeDocument[] = documentPayload.documents.map((d) => ({
          id: String(d.id),
          title: d.title,
          categoryId: "all",
          tags: [d.source_type || "manual"],
          updatedAt: d.updated_at,
          author: d.equipment_type || d.source_name || "系统",
          status: d.status === "published" ? "published" : "draft",
          permission: "editable",
          abstract: `${d.equipment_type}${d.equipment_model ? ` / ${d.equipment_model}` : ""}`,
          revisions: [],
        }))
        const stagedImports: KnowledgeDocument[] = importPayload.jobs
          .filter((job) => !job.document_id && job.status !== "completed")
          .map((job) => ({
            id: `import-${job.id}`,
            title: job.title || job.source_name || `导入任务 #${job.id}`,
            categoryId: "all",
            tags: [job.status === "failed" ? "failed" : "pending", job.source_type || "manual"],
            updatedAt: job.updated_at,
            author: job.equipment_type || "导入任务",
            status: "draft",
            permission: "readonly",
            abstract:
              job.status === "failed"
                ? job.error_message || "文档解析失败，请检查文件内容后重试"
                : job.processing_note || job.preview_excerpt || "文档已上传，正在解析切分并建立索引",
            revisions: [],
            isImportJob: true,
            importJobId: job.id,
            importStatus: job.status,
            errorMessage: job.error_message || undefined,
          }))
        const mergedDocs = [...stagedImports, ...mappedDocs]
        const highlightedJob = highlightImportJobId
          ? importPayload.jobs.find((job) => String(job.id) === highlightImportJobId)
          : null
        const preferredSelectionId = highlightedJob
          ? highlightedJob.document_id
            ? String(highlightedJob.document_id)
            : `import-${highlightedJob.id}`
          : null
        setApiDocs(mergedDocs)
        setSelectedDoc((prev) => {
          if (preferredSelectionId) {
            const highlighted = mergedDocs.find((item) => item.id === preferredSelectionId)
            if (highlighted) return highlighted
          }
          if (prev) {
            const matched = mergedDocs.find((item) => item.id === prev.id)
            if (matched) return matched
          }
          return mergedDocs[0] ?? null
        })
        setImportingCount(importPayload.jobs.filter((job) => job.status === "pending" || job.status === "processing").length)
        setFailedImportCount(importPayload.jobs.filter((job) => job.status === "failed").length)
      } finally {
        if (!options?.silent) {
          setIsLoading(false)
        }
      }
    },
    [highlightImportJobId],
  )

  useEffect(() => {
    void loadKnowledgeState()
  }, [loadKnowledgeState])

  useEffect(() => {
    if (importingCount <= 0) return
    const timer = window.setInterval(() => {
      void loadKnowledgeState({ silent: true })
    }, 3000)
    return () => window.clearInterval(timer)
  }, [importingCount, loadKnowledgeState])

  useEffect(() => {
    if (!fromCases) return
    void (async () => {
      setIsLoading(true)
      try {
        await loadKnowledgeState()
        toast.success("已进入知识文档管理，正在同步最新上传状态")
      } finally {
        setIsLoading(false)
      }
    })()
  }, [fromCases, loadKnowledgeState])

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const doc of apiDocs) {
      const tag = doc.tags[0] || "manual"
      counts[tag] = (counts[tag] || 0) + 1
    }
    return counts
  }, [apiDocs])

  const categoryTree: KnowledgeCategory[] = [
    {
      id: "all",
      name: "全部文档",
      icon: <FileText className="w-4 h-4" />,
      count: apiDocs.length,
      children: [
        { id: "manual", name: "设备手册", icon: <FileText className="w-4 h-4" />, count: typeCounts["manual"] || 0 },
        { id: "sop", name: "SOP流程", icon: <FolderTree className="w-4 h-4" />, count: (typeCounts["sop"] || 0) + (typeCounts["procedure"] || 0) },
        { id: "case", name: "故障案例", icon: <BookOpen className="w-4 h-4" />, count: typeCounts["case"] || 0 },
        { id: "expert", name: "专家经验", icon: <Star className="w-4 h-4" />, count: typeCounts["expert"] || 0 },
        { id: "pending", name: "处理中", icon: <Clock className="w-4 h-4" />, count: importingCount },
        { id: "failed", name: "解析失败", icon: <AlertTriangle className="w-4 h-4" />, count: failedImportCount },
      ],
    },
  ]

  const filteredDocs = apiDocs.filter((doc) => {
    const matchesSearch =
      searchQuery === "" ||
      doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesCategory =
      !selectedCategory ||
      selectedCategory === "all" ||
      doc.categoryId === selectedCategory ||
      doc.tags.includes(selectedCategory)
    return matchesSearch && matchesCategory
  })

  const sortedDocs = [...filteredDocs].sort((a, b) => {
    if (sortBy === "updated") {
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    }
    return a.title.localeCompare(b.title)
  })

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="app-main app-main-wide">
        <section className="mb-3">
          {fromCases ? (
            <Link
              href="/cases"
              className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回知识案例库
            </Link>
          ) : null}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link href="/cases" className="transition-colors hover:text-foreground">知识案例库</Link>
            <ChevronRight className="h-3 w-3" />
            <span className="text-foreground">知识文档管理</span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="mt-2 text-xl font-semibold text-foreground">知识文档管理</h1>
              <p className="mt-1 text-sm text-muted-foreground">上传设备手册、SOP、检修规范和现场图片，构建可检索知识库。</p>
            </div>
            <Link
              href="/knowledge/graph"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-md border border-[#5e6ad2]/30 text-[#5e6ad2] hover:bg-[#5e6ad2]/10 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><circle cx="18" cy="6" r="3"/><line x1="8.5" y1="7.5" x2="15.5" y2="16.5"/><line x1="15.5" y1="7.5" x2="8.5" y2="16.5"/></svg>
              知识图谱
            </Link>
          </div>
        </section>

        {importingCount > 0 || failedImportCount > 0 ? (
          <section className="mb-4">
            <div className="app-card flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {importingCount > 0 ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-emerald-400">
                    <RefreshCw className="h-3.5 w-3.5" />
                    {importingCount} 个导入任务正在处理中
                  </span>
                ) : null}
                {failedImportCount > 0 ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {failedImportCount} 个导入任务解析失败
                  </span>
                ) : null}
                <span className="text-muted-foreground">列表会自动刷新，完成后文档将直接出现在下方。</span>
              </div>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
                onClick={() => {
                  void loadKnowledgeState()
                }}
              >
                <RefreshCw className="h-4 w-4" />
                立即刷新
              </button>
            </div>
          </section>
        ) : null}

        <div className="flex gap-6">
          <aside className="hidden md:block w-64 shrink-0">
            <div className="sticky top-20 app-card p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium text-foreground">知识分类</h2>
                <button
                  type="button"
                  className="rounded p-1 transition-colors hover:bg-muted"
                  onClick={() => {
                    void loadKnowledgeState({ silent: true })
                  }}
                >
                  <FolderOpen className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>
              <CategoryTree
                categories={categoryTree}
                selectedCategory={selectedCategory}
                onSelect={setSelectedCategory}
                expandedIds={expandedIds}
                onToggle={handleToggle}
              />
            </div>
          </aside>

          <div className={`flex-1 min-w-0 ${showMobilePreview ? "hidden lg:block" : ""}`}>
            <div className="app-card overflow-hidden">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-foreground">共 {sortedDocs.length} 条记录</span>
                </div>
                <div className="flex items-center gap-2 lg:hidden">
                  <button
                    type="button"
                    onClick={() => {
                      setSortBy(sortBy === "updated" ? "title" : "updated")
                      void loadKnowledgeState({ silent: true })
                    }}
                    className="rounded-lg p-2 transition-colors hover:bg-muted"
                  >
                    <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
                  </button>
                  <button
                    type="button"
                    className="rounded-lg p-2 transition-colors hover:bg-muted"
                    onClick={() => {
                      void loadKnowledgeState({ silent: true })
                    }}
                  >
                    <Filter className="h-4 w-4 text-muted-foreground" />
                  </button>
                </div>
              </div>

              <div className="max-h-[calc(100vh-220px)] overflow-y-auto">
                {isLoading ? (
                  <DocumentListSkeleton />
                ) : sortedDocs.length === 0 ? (
                  <div className="p-8 text-center">
                    <div className="app-empty-icon mx-auto mb-3 h-12 w-12 rounded-xl">
                      <Search className="h-5 w-5" />
                    </div>
                    <p className="text-sm text-muted-foreground">未找到匹配的文档</p>
                  </div>
                ) : (
                  sortedDocs.map((doc) => (
                    <DocumentListItem
                      key={doc.id}
                      doc={doc}
                      isSelected={selectedDoc?.id === doc.id}
                      onOpenDetail={() => openDocumentDetail(doc)}
                      onClick={() => {
                        setSelectedDoc(doc)
                        setShowMobilePreview(true)
                      }}
                    />
                  ))
                )}
              </div>
            </div>
          </div>

          <aside className={`lg:w-80 xl:w-96 shrink-0 ${showMobilePreview ? "w-full" : "hidden lg:block"}`}>
            <div className="sticky top-20 app-card overflow-hidden">
              {showMobilePreview && (
                <div className="border-b border-border px-4 py-3 lg:hidden">
                  <button
                    type="button"
                    onClick={() => setShowMobilePreview(false)}
                    className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    返回列表
                  </button>
                </div>
              )}

              {selectedDoc ? (
                <div className="max-h-[calc(100vh-220px)] overflow-y-auto">
                  <div className="border-b border-border p-4">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <h3 className="font-medium leading-tight text-foreground">{selectedDoc.title}</h3>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            type="button"
                            className="shrink-0 rounded-lg p-1.5 transition-colors hover:bg-muted"
                            aria-label="更多操作"
                          >
                            <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-44 border-border bg-popover text-popover-foreground">
                          <DropdownMenuItem onClick={() => openDocumentDetail(selectedDoc)}>
                            <Eye className="mr-2 h-4 w-4" />
                            查看详情
                          </DropdownMenuItem>
                          {!selectedDoc.isImportJob ? (
                            <DropdownMenuItem onClick={() => void copyDocumentLink(selectedDoc)}>
                              <Copy className="mr-2 h-4 w-4" />
                              复制链接
                            </DropdownMenuItem>
                          ) : null}
                          <DropdownMenuItem onClick={() => toast.info("编辑能力暂未接入，下一步可以补文档元信息编辑面板。")}>
                            <Edit3 className="mr-2 h-4 w-4" />
                            编辑文档
                          </DropdownMenuItem>
                          <DropdownMenuSeparator className="bg-border" />
                          {!selectedDoc.isImportJob ? (
                            <DropdownMenuItem
                              className="text-red-500 focus:text-red-500"
                              onClick={() => setDeleteTarget(selectedDoc)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              删除文档
                            </DropdownMenuItem>
                          ) : selectedDoc.importStatus === "failed" ? (
                            <DropdownMenuItem
                              className="text-red-500 focus:text-red-500"
                              onClick={() => setDeleteTarget(selectedDoc)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              删除记录
                            </DropdownMenuItem>
                          ) : null}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>

                    <div className="mb-2 flex items-center gap-2">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          selectedDoc.isImportJob
                            ? selectedDoc.importStatus === "failed"
                              ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : selectedDoc.status === "published"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        }`}
                      >
                        {selectedDoc.isImportJob
                          ? selectedDoc.importStatus === "failed"
                            ? "解析失败"
                            : "导入中"
                          : selectedDoc.status === "published"
                            ? "已发布"
                            : "草稿"}
                      </span>
                    </div>
                    <button
                      type="button"
                      className={`group flex w-full items-start gap-2 rounded-lg border border-transparent px-2 py-2 -mx-2 text-left transition-colors ${
                        selectedDoc.isImportJob ? "cursor-default" : "hover:border-border hover:bg-muted/55"
                      }`}
                      onClick={() => {
                        if (!selectedDoc.isImportJob) {
                          openDocumentDetail(selectedDoc)
                        }
                      }}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-xs text-muted-foreground">
                          {selectedDoc.isImportJob ? "导入状态" : "来源摘要"}
                        </div>
                        <div className="truncate text-sm text-foreground">
                          {selectedDoc.abstract || "查看文档详情与分段预览"}
                        </div>
                      </div>
                      {!selectedDoc.isImportJob ? (
                        <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground" />
                      ) : null}
                    </button>
                  </div>
                  <div className="p-4">
                    <div className="grid grid-cols-2 gap-2">
                      {selectedDoc.isImportJob ? (
                        <button
                          type="button"
                          className="col-span-2 flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-muted/35 text-sm text-foreground transition-colors hover:bg-muted"
                          onClick={() => {
                            void loadKnowledgeState()
                          }}
                        >
                          <RefreshCw className="h-4 w-4" />
                          刷新导入状态
                        </button>
                      ) : (
                        <>
                          <Link
                            href={`/knowledge/${selectedDoc.id}`}
                            className="flex h-9 items-center justify-center gap-1.5 rounded-lg bg-[#5e6ad2] text-sm font-medium text-white transition-colors hover:bg-[#6b77db]"
                          >
                            <Eye className="w-4 h-4" />
                            查看详情
                          </Link>
                          <button
                            type="button"
                            className="flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-muted/35 text-sm text-foreground transition-colors hover:bg-muted"
                            onClick={() => {
                              toast.info("编辑能力暂未接入，当前可先通过详情页查看文档内容与分段。")
                            }}
                          >
                            <Edit3 className="w-4 h-4" />
                            编辑
                          </button>
                        </>
                      )}
                    </div>
                    <div className="mt-3 flex items-center justify-center gap-4 border-t border-border pt-3">
                      {!selectedDoc.isImportJob ? (
                        <button
                          type="button"
                          className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                          onClick={() => {
                            void copyDocumentLink(selectedDoc)
                          }}
                        >
                          <Copy className="w-3.5 h-3.5" />
                          复制链接
                        </button>
                      ) : null}
                      {!selectedDoc.isImportJob ? (
                        <button
                          type="button"
                          className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-red-400"
                          onClick={() => {
                            setDeleteTarget(selectedDoc)
                          }}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          删除
                        </button>
                      ) : selectedDoc.importStatus === "failed" ? (
                        <button
                          type="button"
                          className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-red-400"
                          onClick={() => {
                            setDeleteTarget(selectedDoc)
                          }}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          删除记录
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyPreview />
              )}
            </div>
          </aside>
        </div>
      </div>

      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent className="border-border bg-popover text-popover-foreground">
          <AlertDialogHeader>
            <AlertDialogTitle>{deleteTarget?.isImportJob ? "确认删除失败记录" : "确认删除知识文档"}</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              {deleteTarget
                ? deleteTarget.isImportJob
                  ? `确定删除失败记录「${deleteTarget.title}」？这只会清理导入历史，不会影响已发布文档。`
                  : `确定删除文档「${deleteTarget.title}」？此操作不可撤销。`
                : "此操作不可撤销。"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-border bg-transparent text-foreground hover:bg-muted hover:text-foreground">
              取消
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={() => {
                if (!deleteTarget) return
                void handleDeleteDocument(deleteTarget)
              }}
            >
              确定删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}


