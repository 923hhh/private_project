"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, BookOpen, Clock3, FileText, Layers3, Loader2, Tag } from "lucide-react"
import { Header } from "@/shared/components/brand/app-header"
import { fetchKnowledgeDocumentChunks, fetchKnowledgeDocumentDetail, type KnowledgeChunkPreview, type KnowledgeDocumentDetail } from "@/features/knowledge/api"
import { formatDateTimeLocal } from "@/shared/lib/utils"

const RANDOM_PREVIEW_COUNT = 8

function labelForSourceType(type: string) {
  switch (type) {
    case "manual":
      return "设备手册"
    case "sop":
    case "procedure":
      return "SOP 流程"
    case "case":
      return "故障案例"
    case "expert":
      return "专家经验"
    case "spec":
      return "检修规范"
    default:
      return type || "未分类"
  }
}

function cleanSummaryText(value: string | null | undefined) {
  return (value || "")
    .replace(/\[第\s*\d+\s*页\]/g, "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+/g, " ")
    .trim()
}

function buildSummaryParagraphs(excerpt: string | null | undefined) {
  const normalized = cleanSummaryText(excerpt)
  return normalized
    .split(/\n+/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 8)
}

function buildStructuredSummaryItems(excerpt: string | null | undefined) {
  return cleanSummaryText(excerpt)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const separatorIndex = line.indexOf("：")
      if (separatorIndex === -1) {
        return null
      }
      const title = line.slice(0, separatorIndex).trim()
      const content = line.slice(separatorIndex + 1).trim()
      if (!title || !content) {
        return null
      }
      return { title, content }
    })
    .filter((item): item is { title: string; content: string } => Boolean(item))
}

function samplePreviewChunks(items: KnowledgeChunkPreview[], count: number) {
  if (items.length <= count) {
    return [...items].sort((left, right) => left.chunk_index - right.chunk_index)
  }
  const pool = [...items]
  for (let index = pool.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1))
    ;[pool[index], pool[swapIndex]] = [pool[swapIndex], pool[index]]
  }
  return pool
    .slice(0, count)
    .sort((left, right) => left.chunk_index - right.chunk_index)
}

export default function KnowledgeDocumentDetailPage() {
  const params = useParams<{ id: string }>()
  const documentId = Number(params?.id)
  const [detail, setDetail] = useState<KnowledgeDocumentDetail | null>(null)
  const [chunks, setChunks] = useState<KnowledgeChunkPreview[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!Number.isFinite(documentId)) {
      setError("文档编号无效")
      setIsLoading(false)
      return
    }
    void (async () => {
      setIsLoading(true)
      setError(null)
      try {
        const detailPayload = await fetchKnowledgeDocumentDetail(documentId)
        const chunksPayload = await fetchKnowledgeDocumentChunks(
          documentId,
          Math.max(detailPayload.chunk_count || RANDOM_PREVIEW_COUNT, RANDOM_PREVIEW_COUNT),
        )
        setDetail(detailPayload)
        setChunks(chunksPayload.chunks)
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载文档详情失败")
      } finally {
        setIsLoading(false)
      }
    })()
  }, [documentId])

  const metadata = useMemo(() => {
    if (!detail) return []
    return [
      { label: "知识类型", value: labelForSourceType(detail.source_type), icon: Tag },
      { label: "设备类型", value: detail.equipment_type || "--", icon: BookOpen },
      { label: "分段数量", value: `${detail.chunk_count} 段`, icon: Layers3 },
      { label: "最近更新", value: formatDateTimeLocal(detail.updated_at), icon: Clock3 },
    ]
  }, [detail])

  const summaryParagraphs = useMemo(
    () => buildSummaryParagraphs(detail?.content_excerpt),
    [detail?.content_excerpt],
  )
  const structuredSummaryItems = useMemo(
    () => buildStructuredSummaryItems(detail?.content_excerpt),
    [detail?.content_excerpt],
  )
  const previewChunks = useMemo(
    () => samplePreviewChunks(chunks, RANDOM_PREVIEW_COUNT),
    [chunks],
  )

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <div className="app-main app-main-wide">
        <div className="mb-4">
          <Link href="/knowledge" className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            返回知识文档管理
          </Link>
        </div>

        {isLoading ? (
          <div className="app-card flex min-h-[320px] items-center justify-center p-8">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>正在加载知识文档详情...</span>
            </div>
          </div>
        ) : error ? (
          <div className="app-card min-h-[260px] p-8">
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="app-empty-icon mb-4 h-14 w-14">
                <FileText className="h-6 w-6" />
              </div>
              <h1 className="text-lg font-semibold text-foreground">无法查看该知识文档</h1>
              <p className="mt-2 max-w-lg text-sm text-muted-foreground">{error}</p>
            </div>
          </div>
        ) : detail ? (
          <div className="space-y-6">
            <section className="app-card p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-500">
                      {detail.status === "published" ? "已发布" : detail.status}
                    </span>
                    <span className="app-chip-muted">{labelForSourceType(detail.source_type)}</span>
                  </div>
                  <h1 className="text-2xl font-semibold text-foreground">{detail.title}</h1>
                  <p className="mt-2 text-sm text-muted-foreground">
                    来源文件：{detail.source_name}
                    {detail.equipment_model ? ` · 型号 ${detail.equipment_model}` : ""}
                    {detail.fault_type ? ` · ${detail.fault_type}` : ""}
                  </p>
                </div>
                <div className="grid w-full gap-3 sm:grid-cols-2 lg:w-[420px]">
                  {metadata.map((item) => {
                    const Icon = item.icon
                    return (
                      <div key={item.label} className="app-subpanel p-4">
                        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                          <Icon className="h-3.5 w-3.5" />
                          {item.label}
                        </div>
                        <div className="text-sm font-medium text-foreground">{item.value}</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </section>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
              <section className="app-card p-6">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">内容摘录与分段预览</h2>
                    <p className="mt-1 text-sm text-muted-foreground">从全文分段中随机抽取部分内容预览，用于回溯知识来源、检查切分效果和定位检索上下文。</p>
                  </div>
                  <span className="app-chip-muted">随机预览 {previewChunks.length} / {detail.chunk_count} 段</span>
                </div>

                {detail.content_excerpt ? (
                  <div className="mb-4 rounded-xl border border-border bg-muted/45 p-4">
                    <div className="mb-2 text-xs font-medium text-muted-foreground">文档摘要</div>
                    {structuredSummaryItems.length > 0 ? (
                      <div className="space-y-3">
                        {structuredSummaryItems.map((item) => (
                          <div key={item.title} className="rounded-lg border border-border bg-background/90 p-3">
                            <div className="text-xs font-medium text-muted-foreground">{item.title}</div>
                            <p className="mt-1 text-sm leading-7 text-foreground">{item.content}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {summaryParagraphs.map((item, index) => (
                          <p key={`${item}-${index}`} className="text-sm leading-7 text-foreground">
                            {item}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}

                <div className="space-y-3">
                  {previewChunks.length > 0 ? (
                    previewChunks.map((chunk) => (
                      <div key={chunk.chunk_id} className="rounded-xl border border-border bg-card p-4">
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                            Chunk {chunk.chunk_index}
                          </span>
                          {chunk.heading ? <span className="text-sm font-medium text-foreground">{chunk.heading}</span> : null}
                          {chunk.page_reference ? <span className="app-chip-muted">页码 {chunk.page_reference}</span> : null}
                          {chunk.section_reference ? <span className="app-chip-muted">{chunk.section_reference}</span> : null}
                        </div>
                        <p className="text-sm leading-6 text-foreground">{chunk.content}</p>
                        {(chunk.section_path || chunk.step_anchor || chunk.image_anchor) ? (
                          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            {chunk.section_path ? <span className="app-chip-muted">路径 {chunk.section_path}</span> : null}
                            {chunk.step_anchor ? <span className="app-chip-muted">步骤 {chunk.step_anchor}</span> : null}
                            {chunk.image_anchor ? <span className="app-chip-muted">图示 {chunk.image_anchor}</span> : null}
                          </div>
                        ) : null}
                      </div>
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-border bg-muted/35 p-8 text-center">
                      <p className="text-sm text-muted-foreground">当前文档暂无可预览分段。</p>
                    </div>
                  )}
                </div>
              </section>

              <aside className="space-y-4">
                <div className="app-card p-5">
                  <h2 className="text-base font-semibold text-foreground">文档定位信息</h2>
                  <dl className="mt-4 space-y-3 text-sm">
                    <div>
                      <dt className="text-xs text-muted-foreground">创建时间</dt>
                      <dd className="mt-1 text-foreground">{formatDateTimeLocal(detail.created_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">章节引用</dt>
                      <dd className="mt-1 text-foreground">{detail.section_reference || "--"}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">页码引用</dt>
                      <dd className="mt-1 text-foreground">{detail.page_reference || "--"}</dd>
                    </div>
                  </dl>
                </div>

                <div className="app-card p-5">
                  <h2 className="text-base font-semibold text-foreground">下一步建议</h2>
                  <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                    <li>确认文档标题、设备类型和来源文件是否与实际资料一致。</li>
                    <li>检查分段预览是否覆盖关键步骤、故障现象和定位描述。</li>
                    <li>如检索命中不理想，可继续补充章节说明或重新导入更清晰版本。</li>
                  </ul>
                </div>
              </aside>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

