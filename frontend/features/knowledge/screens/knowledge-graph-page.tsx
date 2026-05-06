"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import Link from "next/link"
import dynamic from "next/dynamic"
import { ArrowLeft, RefreshCw, Filter } from "lucide-react"
import { Header } from "@/shared/components/brand/app-header"
import {
  fetchKnowledgeGraph,
  fetchKnowledgeGraphStats,
  type GraphNode,
  type GraphEdge,
  type GraphStatsResponse,
} from "@/features/knowledge/api"

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false })

const KIND_COLORS: Record<string, string> = {
  maintenance_case: "#f59e0b",
  knowledge_document: "#3b82f6",
  knowledge_chunk: "#14b8a6",
  maintenance_task: "#a855f7",
}

const KIND_LABELS: Record<string, string> = {
  maintenance_case: "检修案例",
  knowledge_document: "知识文档",
  knowledge_chunk: "知识分段",
  maintenance_task: "检修任务",
}

const RELATION_LABELS: Record<string, string> = {
  derived_from: "来源于",
  references: "引用",
  approved_into: "沉淀为",
  cites: "引用",
  corrected: "已修正",
  published_into: "发布为",
}

/* ---- GRAPH PAGE COMPONENT ---- */

interface GraphData {
  nodes: Array<GraphNode & { color?: string }>
  links: Array<{ source: string; target: string; relation_type: string; id: number }>
}

export default function KnowledgeGraphPage() {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] })
  const [stats, setStats] = useState<GraphStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [filterKind, setFilterKind] = useState<string>("")
  const [filterRelation, setFilterRelation] = useState<string>("")
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

  const loadGraph = useCallback(async () => {
    setLoading(true)
    try {
      const [graph, s] = await Promise.all([
        fetchKnowledgeGraph({
          kind: filterKind || undefined,
          relation_type: filterRelation || undefined,
          limit: 300,
        }),
        fetchKnowledgeGraphStats(),
      ])
      setStats(s)
      setGraphData({
        nodes: graph.nodes.map((n) => ({ ...n, color: KIND_COLORS[n.kind] || "#6b7280" })),
        links: graph.edges.map((e) => ({
          source: e.source,
          target: e.target,
          relation_type: e.relation_type,
          id: e.id,
        })),
      })
    } catch {
      /* silent */
    } finally {
      setLoading(false)
    }
  }, [filterKind, filterRelation])

  useEffect(() => { void loadGraph() }, [loadGraph])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="app-main app-main-wide">
        <section className="app-page-head flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/knowledge" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="w-4 h-4" />
              返回知识库
            </Link>
            <h1 className="text-lg font-semibold text-foreground">知识图谱</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <select className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground" value={filterKind} onChange={(e) => setFilterKind(e.target.value)}>
                <option value="">全部类型</option>
                {Object.entries(KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <select className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground" value={filterRelation} onChange={(e) => setFilterRelation(e.target.value)}>
                <option value="">全部关系</option>
                {Object.entries(RELATION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <button onClick={() => void loadGraph()} disabled={loading} className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors disabled:opacity-50">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              刷新
            </button>
          </div>
        </section>

        <div className="relative flex gap-4" style={{ height: "calc(100vh - 160px)" }}>
          {/* 图谱画布 */}
          <div ref={containerRef} className="flex-1 rounded-xl border border-border bg-[#08090a] overflow-hidden">
            {graphData.nodes.length > 0 ? (
              <ForceGraph2D
                width={dimensions.width}
                height={dimensions.height}
                graphData={graphData as any}
                nodeLabel={(node: any) => `${KIND_LABELS[node.kind] || node.kind}: ${node.label}`}
                nodeColor={(node: any) => node.color || "#6b7280"}
                nodeRelSize={6}
                linkDirectionalArrowLength={4}
                linkDirectionalArrowRelPos={1}
                linkColor={() => "rgba(255,255,255,0.12)"}
                linkLabel={(link: any) => RELATION_LABELS[link.relation_type] || link.relation_type}
                onNodeClick={(node: any) => setSelectedNode(node as GraphNode)}
                backgroundColor="#08090a"
                nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                  const x = node.x ?? 0
                  const y = node.y ?? 0
                  const r = 5
                  ctx.beginPath()
                  ctx.arc(x, y, r, 0, 2 * Math.PI)
                  ctx.fillStyle = node.color || "#6b7280"
                  ctx.fill()
                  if (globalScale > 1.5) {
                    ctx.font = `${10 / globalScale}px sans-serif`
                    ctx.fillStyle = "rgba(255,255,255,0.8)"
                    ctx.textAlign = "center"
                    ctx.fillText((node.label || "").slice(0, 12), x, y + r + 10 / globalScale)
                  }
                }}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                {loading ? "加载中..." : "暂无图谱数据，请先通过审核案例或创建检修任务以生成知识关系"}
              </div>
            )}
          </div>

          {/* 右侧面板 */}
          <aside className="hidden lg:flex w-64 flex-col gap-4">
            {/* 统计 */}
            <div className="rounded-xl border border-border bg-card p-4">
              <h3 className="text-sm font-medium text-foreground mb-3">图谱统计</h3>
              {stats ? (
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">节点总数</span><span className="text-foreground font-medium">{stats.total_nodes}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">关系总数</span><span className="text-foreground font-medium">{stats.total_edges}</span></div>
                  <div className="border-t border-border my-2" />
                  <p className="text-xs text-muted-foreground mb-1">按类型</p>
                  {Object.entries(stats.nodes_by_kind).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: KIND_COLORS[k] || "#6b7280" }} />
                        {KIND_LABELS[k] || k}
                      </span>
                      <span className="text-foreground">{v}</span>
                    </div>
                  ))}
                  <div className="border-t border-border my-2" />
                  <p className="text-xs text-muted-foreground mb-1">按关系</p>
                  {Object.entries(stats.edges_by_type).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-muted-foreground">{RELATION_LABELS[k] || k}</span>
                      <span className="text-foreground">{v}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">加载中...</p>
              )}
            </div>

            {/* 选中节点详情 */}
            {selectedNode && (
              <div className="rounded-xl border border-border bg-card p-4">
                <h3 className="text-sm font-medium text-foreground mb-3">节点详情</h3>
                <div className="space-y-2 text-sm">
                  <div><span className="text-muted-foreground">类型：</span><span className="text-foreground">{KIND_LABELS[selectedNode.kind] || selectedNode.kind}</span></div>
                  <div><span className="text-muted-foreground">标签：</span><span className="text-foreground">{selectedNode.label}</span></div>
                  {Object.entries(selectedNode.properties).map(([k, v]) => (
                    <div key={k}><span className="text-muted-foreground">{k}：</span><span className="text-foreground">{String(v)}</span></div>
                  ))}
                </div>
              </div>
            )}

            {/* 图例 */}
            <div className="rounded-xl border border-border bg-card p-4">
              <h3 className="text-sm font-medium text-foreground mb-3">图例</h3>
              <div className="space-y-2">
                {Object.entries(KIND_LABELS).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 text-sm">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: KIND_COLORS[k] }} />
                    <span className="text-muted-foreground">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  )
}

