"use client"

import { useEffect, useState, useCallback, useRef, useMemo } from "react"
import Link from "next/link"
import dynamic from "next/dynamic"
import { ArrowLeft, RefreshCw, Filter, Network, Sparkles } from "lucide-react"
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

type GraphNodeLevel = 0 | 1 | 2 | 3

type VisualNode = GraphNode & {
  color: string
  degree: number
  level: GraphNodeLevel
  branchKey: string
  x?: number
  y?: number
}

type VisualLink = {
  id: number
  source: string | VisualNode
  target: string | VisualNode
  relation_type: string
  notes: string | null
  created_at: string
  color: string
}

interface GraphData {
  nodes: VisualNode[]
  links: VisualLink[]
}

function hexToRgba(hex: string, alpha: number): string {
  const normalized = hex.replace("#", "")
  const value =
    normalized.length === 3
      ? normalized
          .split("")
          .map((char) => `${char}${char}`)
          .join("")
      : normalized
  const num = Number.parseInt(value, 16)
  const r = (num >> 16) & 255
  const g = (num >> 8) & 255
  const b = num & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function polarToXY(radius: number, angle: number) {
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
  }
}

function buildGraphData(nodes: GraphNode[], edges: GraphEdge[]): GraphData {
  if (nodes.length === 0) {
    return { nodes: [], links: [] }
  }

  const byId = new Map(nodes.map((node) => [node.id, node]))
  const adjacency = new Map<string, Set<string>>()
  const degree = new Map<string, number>()
  for (const node of nodes) {
    adjacency.set(node.id, new Set())
    degree.set(node.id, 0)
  }

  for (const edge of edges) {
    adjacency.get(edge.source)?.add(edge.target)
    adjacency.get(edge.target)?.add(edge.source)
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1)
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1)
  }

  const sortedNodes = [...nodes].sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))
  const centerId = sortedNodes[0]?.id ?? nodes[0].id
  const centerNeighbors = [...(adjacency.get(centerId) ?? new Set<string>())].sort(
    (a, b) => (degree.get(b) ?? 0) - (degree.get(a) ?? 0),
  )

  const levels = new Map<string, GraphNodeLevel>()
  const branchKeys = new Map<string, string>()
  levels.set(centerId, 0)
  branchKeys.set(centerId, centerId)

  centerNeighbors.forEach((nodeId) => {
    levels.set(nodeId, 1)
    branchKeys.set(nodeId, nodeId)
  })

  const queue = [...centerNeighbors]
  while (queue.length > 0) {
    const current = queue.shift()
    if (!current) continue
    const currentLevel = levels.get(current) ?? 1
    if (currentLevel >= 3) continue

    for (const neighbor of adjacency.get(current) ?? []) {
      if (!levels.has(neighbor)) {
        const nextLevel = Math.min(3, currentLevel + 1) as GraphNodeLevel
        levels.set(neighbor, nextLevel)
        branchKeys.set(neighbor, branchKeys.get(current) ?? current)
        queue.push(neighbor)
      }
    }
  }

  for (const node of nodes) {
    if (!levels.has(node.id)) {
      levels.set(node.id, 3)
      branchKeys.set(node.id, centerNeighbors[0] ?? centerId)
    }
  }

  const positionedNodes = new Map<string, VisualNode>()
  const centerNode = byId.get(centerId) ?? nodes[0]
  positionedNodes.set(centerId, {
    ...centerNode,
    color: KIND_COLORS[centerNode.kind] || "#64748b",
    degree: degree.get(centerId) ?? 0,
    level: 0,
    branchKey: centerId,
    x: 0,
    y: 0,
  })

  const branchAngles = new Map<string, number>()
  const primaryRadius = nodes.length <= 6 ? 150 : 205
  const secondaryRadius = nodes.length <= 10 ? 260 : 330
  const tertiaryRadius = nodes.length <= 14 ? 390 : 455
  const baseAngle = -Math.PI / 2
  const angleStep = (Math.PI * 2) / Math.max(centerNeighbors.length, 1)

  centerNeighbors.forEach((nodeId, index) => {
    const node = byId.get(nodeId)
    if (!node) return
    const angle = baseAngle + angleStep * index
    const point = polarToXY(primaryRadius, angle)
    branchAngles.set(nodeId, angle)
    positionedNodes.set(nodeId, {
      ...node,
      color: KIND_COLORS[node.kind] || "#64748b",
      degree: degree.get(nodeId) ?? 0,
      level: 1,
      branchKey: nodeId,
      x: point.x,
      y: point.y,
    })
  })

  const grouped = new Map<string, string[]>()
  for (const node of nodes) {
    if (node.id === centerId || centerNeighbors.includes(node.id)) continue
    const branchKey = branchKeys.get(node.id) ?? centerId
    const bucket = grouped.get(branchKey) ?? []
    bucket.push(node.id)
    grouped.set(branchKey, bucket)
  }

  for (const [branchKey, nodeIds] of grouped.entries()) {
    const baseBranchAngle = branchAngles.get(branchKey) ?? baseAngle
    const sorted = nodeIds.sort((a, b) => (degree.get(b) ?? 0) - (degree.get(a) ?? 0))
    const spread = Math.min(Math.PI / 2.5, 0.38 + sorted.length * 0.07)
    const innerDenominator = Math.max(sorted.length - 1, 1)

    sorted.forEach((nodeId, index) => {
      const node = byId.get(nodeId)
      if (!node) return
      const level = levels.get(nodeId) ?? 3
      const offset =
        sorted.length === 1 ? 0 : -spread / 2 + (spread * index) / innerDenominator
      const angle = baseBranchAngle + offset
      const radius = level === 2 ? secondaryRadius : tertiaryRadius
      const point = polarToXY(radius, angle)
      positionedNodes.set(nodeId, {
        ...node,
        color: KIND_COLORS[node.kind] || "#64748b",
        degree: degree.get(nodeId) ?? 0,
        level,
        branchKey,
        x: point.x,
        y: point.y,
      })
    })
  }

  const visualNodes = nodes.map((node) => {
    const fallbackAngle = (Math.PI * 2 * nodes.findIndex((item) => item.id === node.id)) / Math.max(nodes.length, 1)
    const fallbackPoint = polarToXY(secondaryRadius, fallbackAngle)
    return (
      positionedNodes.get(node.id) ?? {
        ...node,
        color: KIND_COLORS[node.kind] || "#64748b",
        degree: degree.get(node.id) ?? 0,
        level: 3,
        branchKey: centerNeighbors[0] ?? centerId,
        x: fallbackPoint.x,
        y: fallbackPoint.y,
      }
    )
  })

  const nodeById = new Map(visualNodes.map((node) => [node.id, node]))
  const visualLinks = edges.map((edge) => {
    const sourceNode = nodeById.get(edge.source)
    const targetNode = nodeById.get(edge.target)
    const branchKey =
      sourceNode?.level === 0
        ? targetNode?.branchKey
        : sourceNode?.branchKey || targetNode?.branchKey || centerId
    const branchNode = nodeById.get(branchKey ?? centerId)
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      relation_type: edge.relation_type,
      notes: edge.notes,
      created_at: edge.created_at,
      color: branchNode?.color || sourceNode?.color || "#94a3b8",
    }
  })

  return { nodes: visualNodes, links: visualLinks }
}

function getNodeRadius(node: VisualNode, selectedId?: string | null): number {
  const isSelected = selectedId === node.id
  if (node.level === 0) return isSelected ? 34 : 30
  if (node.level === 1) return isSelected ? 16 : 13
  const degreeBoost = Math.min(node.degree, 4) * 0.7
  return (isSelected ? 10 : 7) + degreeBoost
}

export default function KnowledgeGraphPage() {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] })
  const [stats, setStats] = useState<GraphStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState<VisualNode | null>(null)
  const [filterKind, setFilterKind] = useState<string>("")
  const [filterRelation, setFilterRelation] = useState<string>("")
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<any>(null)
  const [dimensions, setDimensions] = useState({ width: 960, height: 700 })

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
      const data = buildGraphData(graph.nodes, graph.edges)
      setStats(s)
      setGraphData(data)
      setSelectedNode((current) => {
        if (!current) return null
        return data.nodes.find((node) => node.id === current.id) ?? null
      })
    } catch {
      /* silent */
    } finally {
      setLoading(false)
    }
  }, [filterKind, filterRelation])

  useEffect(() => {
    void loadGraph()
  }, [loadGraph])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!graphRef.current || graphData.nodes.length === 0) return
    const timer = window.setTimeout(() => {
      graphRef.current.d3Force("charge")?.strength(-55)
      graphRef.current.d3Force("collide")?.radius((node: VisualNode) => getNodeRadius(node) + 28)
      graphRef.current.d3Force("link")?.distance((link: VisualLink) => {
        const source = typeof link.source === "object" ? link.source : graphData.nodes.find((node) => node.id === link.source)
        const target = typeof link.target === "object" ? link.target : graphData.nodes.find((node) => node.id === link.target)
        if (!source || !target) return 115
        if (source.level === 0 || target.level === 0) return 118
        if (source.level === 1 || target.level === 1) return 96
        return 84
      })
      graphRef.current.zoomToFit(450, 88)
    }, 100)
    return () => window.clearTimeout(timer)
  }, [graphData])

  const selectedNodeId = selectedNode?.id ?? null

  const selectedRelations = useMemo(() => {
    if (!selectedNodeId) return []
    return graphData.links
      .filter((link) => {
        const sourceId = typeof link.source === "object" ? link.source.id : link.source
        const targetId = typeof link.target === "object" ? link.target.id : link.target
        return sourceId === selectedNodeId || targetId === selectedNodeId
      })
      .map((link) => {
        const sourceId = typeof link.source === "object" ? link.source.id : link.source
        const targetId = typeof link.target === "object" ? link.target.id : link.target
        const neighborId = sourceId === selectedNodeId ? targetId : sourceId
        const neighbor = graphData.nodes.find((node) => node.id === neighborId)
        return {
          id: link.id,
          relationType: RELATION_LABELS[link.relation_type] || link.relation_type,
          neighborLabel: neighbor?.label || neighborId,
          neighborKind: neighbor ? KIND_LABELS[neighbor.kind] || neighbor.kind : "关联节点",
          color: neighbor?.color || link.color,
        }
      })
  }, [graphData, selectedNodeId])

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="app-main app-main-wide">
        <section className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/knowledge"
              className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              返回知识库
            </Link>
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs text-cyan-700">
                <Network className="h-3.5 w-3.5" />
                关系结构视图
              </div>
              <h1 className="mt-2 text-xl font-semibold text-foreground">知识图谱</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                以中心辐射方式查看任务、案例、文档与知识分段之间的连接关系
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 shadow-sm">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                value={filterKind}
                onChange={(e) => setFilterKind(e.target.value)}
              >
                <option value="">全部类型</option>
                {Object.entries(KIND_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <select
                className="h-8 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                value={filterRelation}
                onChange={(e) => setFilterRelation(e.target.value)}
              >
                <option value="">全部关系</option>
                {Object.entries(RELATION_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => void loadGraph()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              刷新
            </button>
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="relative overflow-hidden rounded-2xl border border-border bg-card shadow-[0_12px_32px_rgba(15,23,42,0.06)]">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.10),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(20,184,166,0.12),transparent_28%),linear-gradient(180deg,#f8fbff_0%,#f1f6fb_100%)]" />
            <div className="pointer-events-none absolute left-5 top-5 z-10 flex items-center gap-2 rounded-full border border-white/70 bg-white/85 px-3 py-1.5 text-xs text-slate-600 shadow-sm backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-cyan-600" />
              拖拽节点、滚轮缩放，点击节点查看一跳连接
            </div>

            <div ref={containerRef} className="relative h-[720px] w-full">
              {graphData.nodes.length > 0 ? (
                <ForceGraph2D
                  ref={graphRef}
                  width={dimensions.width}
                  height={dimensions.height}
                  graphData={graphData as any}
                  backgroundColor="#f6f9fc"
                  cooldownTicks={120}
                  d3AlphaDecay={0.04}
                  d3VelocityDecay={0.32}
                  nodeLabel={(node: VisualNode) => `${KIND_LABELS[node.kind] || node.kind}: ${node.label}`}
                  linkLabel={(link: VisualLink) => RELATION_LABELS[link.relation_type] || link.relation_type}
                  linkDirectionalArrowLength={3.2}
                  linkDirectionalArrowRelPos={1}
                  linkCurvature={(link: VisualLink) => {
                    const source = typeof link.source === "object" ? link.source : graphData.nodes.find((node) => node.id === link.source)
                    const target = typeof link.target === "object" ? link.target : graphData.nodes.find((node) => node.id === link.target)
                    if (!source || !target) return 0.08
                    if (source.level === 0 || target.level === 0) return 0.18
                    if (source.branchKey === target.branchKey) return 0.1
                    return 0.2
                  }}
                  linkWidth={(link: VisualLink) => {
                    const sourceId = typeof link.source === "object" ? link.source.id : link.source
                    const targetId = typeof link.target === "object" ? link.target.id : link.target
                    if (selectedNodeId && (sourceId === selectedNodeId || targetId === selectedNodeId)) {
                      return 2.8
                    }
                    return 1.4
                  }}
                  linkColor={(link: VisualLink) => {
                    const sourceId = typeof link.source === "object" ? link.source.id : link.source
                    const targetId = typeof link.target === "object" ? link.target.id : link.target
                    if (selectedNodeId && (sourceId === selectedNodeId || targetId === selectedNodeId)) {
                      return hexToRgba(link.color, 0.65)
                    }
                    if (selectedNodeId) {
                      return "rgba(148,163,184,0.18)"
                    }
                    return hexToRgba(link.color, 0.28)
                  }}
                  linkDirectionalParticles={(link: VisualLink) => {
                    const sourceId = typeof link.source === "object" ? link.source.id : link.source
                    const targetId = typeof link.target === "object" ? link.target.id : link.target
                    return selectedNodeId && (sourceId === selectedNodeId || targetId === selectedNodeId) ? 2 : 0
                  }}
                  linkDirectionalParticleColor={(link: VisualLink) => link.color}
                  linkDirectionalParticleWidth={2.4}
                  onNodeClick={(node: VisualNode) => {
                    setSelectedNode(node)
                    graphRef.current?.centerAt(node.x ?? 0, node.y ?? 0, 400)
                    graphRef.current?.zoom(2.1, 400)
                  }}
                  onBackgroundClick={() => setSelectedNode(null)}
                  nodeCanvasObject={(node: VisualNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
                    const x = node.x ?? 0
                    const y = node.y ?? 0
                    const radius = getNodeRadius(node, selectedNodeId)
                    const label = (node.label || "").trim()
                    const isSelected = selectedNodeId === node.id
                    const isDimmed = Boolean(selectedNodeId && !isSelected && !selectedRelations.find((item) => item.neighborLabel === node.label))
                    const textColor = isDimmed ? "rgba(71,85,105,0.42)" : "rgba(15,23,42,0.92)"

                    ctx.save()

                    ctx.beginPath()
                    ctx.fillStyle = hexToRgba(node.color, node.level === 0 ? 0.16 : 0.1)
                    ctx.arc(x, y, radius * (node.level === 0 ? 2.45 : 2.0), 0, Math.PI * 2)
                    ctx.fill()

                    if (node.level <= 1) {
                      const fontSize = node.level === 0 ? 17 : 12
                      ctx.font = `${fontSize}px sans-serif`
                      const textWidth = ctx.measureText(label).width
                      const padX = node.level === 0 ? 18 : 10
                      const padY = node.level === 0 ? 10 : 8
                      const boxWidth = Math.max(radius * 2, textWidth + padX * 2)
                      const boxHeight = fontSize + padY * 2
                      const boxX = x - boxWidth / 2
                      const boxY = y - boxHeight / 2

                      ctx.beginPath()
                      ctx.fillStyle = isDimmed ? "rgba(255,255,255,0.45)" : hexToRgba(node.color, node.level === 0 ? 0.92 : 0.88)
                      ctx.strokeStyle = isSelected ? hexToRgba(node.color, 0.95) : hexToRgba(node.color, 0.35)
                      ctx.lineWidth = isSelected ? 2.4 : 1.2
                      const radiusBox = node.level === 0 ? 20 : 12
                      ctx.moveTo(boxX + radiusBox, boxY)
                      ctx.lineTo(boxX + boxWidth - radiusBox, boxY)
                      ctx.quadraticCurveTo(boxX + boxWidth, boxY, boxX + boxWidth, boxY + radiusBox)
                      ctx.lineTo(boxX + boxWidth, boxY + boxHeight - radiusBox)
                      ctx.quadraticCurveTo(boxX + boxWidth, boxY + boxHeight, boxX + boxWidth - radiusBox, boxY + boxHeight)
                      ctx.lineTo(boxX + radiusBox, boxY + boxHeight)
                      ctx.quadraticCurveTo(boxX, boxY + boxHeight, boxX, boxY + boxHeight - radiusBox)
                      ctx.lineTo(boxX, boxY + radiusBox)
                      ctx.quadraticCurveTo(boxX, boxY, boxX + radiusBox, boxY)
                      ctx.closePath()
                      ctx.shadowColor = hexToRgba(node.color, node.level === 0 ? 0.2 : 0.12)
                      ctx.shadowBlur = node.level === 0 ? 20 : 10
                      ctx.fill()
                      ctx.shadowBlur = 0
                      ctx.stroke()

                      ctx.fillStyle = node.level === 0 ? "white" : "rgba(255,255,255,0.97)"
                      ctx.textAlign = "center"
                      ctx.textBaseline = "middle"
                      ctx.fillText(label.length > (node.level === 0 ? 14 : 10) ? `${label.slice(0, node.level === 0 ? 14 : 10)}...` : label, x, y + 0.5)
                    } else {
                      ctx.beginPath()
                      ctx.fillStyle = isDimmed ? "rgba(255,255,255,0.45)" : node.color
                      ctx.shadowColor = hexToRgba(node.color, 0.28)
                      ctx.shadowBlur = 10
                      ctx.arc(x, y, radius, 0, Math.PI * 2)
                      ctx.fill()
                      ctx.shadowBlur = 0

                      const showLabel = globalScale > 0.9 || node.degree >= 2 || isSelected
                      if (showLabel && label) {
                        ctx.font = `${Math.max(10, 12 - Math.log(globalScale + 1))}px sans-serif`
                        ctx.fillStyle = textColor
                        ctx.textAlign = x >= 0 ? "left" : "right"
                        ctx.textBaseline = "middle"
                        const offset = radius + 8
                        ctx.fillText(label.length > 16 ? `${label.slice(0, 16)}...` : label, x >= 0 ? x + offset : x - offset, y)
                      }
                    }

                    ctx.restore()
                  }}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  {loading ? "加载图谱中..." : "暂无图谱数据，请先通过审核案例或创建检修任务以生成知识关系"}
                </div>
              )}
            </div>
          </div>

          <aside className="flex flex-col gap-4">
            <div className="rounded-2xl border border-border bg-card p-4 shadow-[0_10px_26px_rgba(15,23,42,0.04)]">
              <h3 className="text-sm font-medium text-foreground">图谱统计</h3>
              {stats ? (
                <div className="mt-4 space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-cyan-100 bg-cyan-50 p-3">
                      <div className="text-xs text-cyan-700">节点总数</div>
                      <div className="mt-1 text-2xl font-semibold text-foreground">{stats.total_nodes}</div>
                    </div>
                    <div className="rounded-xl border border-violet-100 bg-violet-50 p-3">
                      <div className="text-xs text-violet-700">关系总数</div>
                      <div className="mt-1 text-2xl font-semibold text-foreground">{stats.total_edges}</div>
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">节点类型</div>
                    <div className="space-y-2">
                      {Object.entries(stats.nodes_by_kind).map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between rounded-xl border border-border bg-background/80 px-3 py-2 text-sm">
                          <span className="flex items-center gap-2 text-muted-foreground">
                            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: KIND_COLORS[key] || "#64748b" }} />
                            {KIND_LABELS[key] || key}
                          </span>
                          <span className="font-medium text-foreground">{value}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">层级说明</div>
                    <div className="space-y-2 text-sm">
                      <div className="rounded-xl border border-border bg-background/80 px-3 py-2">
                        <div className="font-medium text-foreground">主中心</div>
                        <div className="mt-1 text-muted-foreground">当前图中连接最密集的核心节点</div>
                      </div>
                      <div className="rounded-xl border border-border bg-background/80 px-3 py-2">
                        <div className="font-medium text-foreground">一级分支</div>
                        <div className="mt-1 text-muted-foreground">与中心直接相连的知识主题或业务实体</div>
                      </div>
                      <div className="rounded-xl border border-border bg-background/80 px-3 py-2">
                        <div className="font-medium text-foreground">普通知识点</div>
                        <div className="mt-1 text-muted-foreground">围绕各分支向外展开的具体连接节点</div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">加载中...</p>
              )}
            </div>

            <div className="rounded-2xl border border-border bg-card p-4 shadow-[0_10px_26px_rgba(15,23,42,0.04)]">
              <h3 className="text-sm font-medium text-foreground">节点详情</h3>
              {selectedNode ? (
                <div className="mt-4 space-y-3 text-sm">
                  <div className="rounded-xl border border-border bg-background/80 p-3">
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: selectedNode.color }} />
                      <span className="font-medium text-foreground">{selectedNode.label}</span>
                    </div>
                    <div className="mt-2 text-muted-foreground">{KIND_LABELS[selectedNode.kind] || selectedNode.kind}</div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-xl border border-border bg-background/80 px-3 py-2">
                      <div className="text-xs text-muted-foreground">连接数</div>
                      <div className="mt-1 font-medium text-foreground">{selectedNode.degree}</div>
                    </div>
                    <div className="rounded-xl border border-border bg-background/80 px-3 py-2">
                      <div className="text-xs text-muted-foreground">层级</div>
                      <div className="mt-1 font-medium text-foreground">
                        {selectedNode.level === 0 ? "主中心" : selectedNode.level === 1 ? "一级分支" : "普通知识点"}
                      </div>
                    </div>
                  </div>

                  {selectedRelations.length > 0 ? (
                    <div>
                      <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">连接方式</div>
                      <div className="space-y-2">
                        {selectedRelations.slice(0, 8).map((item) => (
                          <div key={item.id} className="rounded-xl border border-border bg-background/80 px-3 py-2">
                            <div className="flex items-center gap-2 text-foreground">
                              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                              <span className="font-medium">{item.neighborLabel}</span>
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {item.neighborKind} · {item.relationType}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {Object.entries(selectedNode.properties).length > 0 ? (
                    <div>
                      <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">节点属性</div>
                      <div className="space-y-2">
                        {Object.entries(selectedNode.properties).map(([key, value]) => (
                          <div key={key} className="rounded-xl border border-border bg-background/80 px-3 py-2">
                            <div className="text-xs text-muted-foreground">{key}</div>
                            <div className="mt-1 break-words text-sm text-foreground">{String(value)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">点击节点后可查看它与其他知识点的连接关系。</p>
              )}
            </div>

            <div className="rounded-2xl border border-border bg-card p-4 shadow-[0_10px_26px_rgba(15,23,42,0.04)]">
              <h3 className="text-sm font-medium text-foreground">关系图例</h3>
              <div className="mt-4 space-y-2">
                {Object.entries(KIND_LABELS).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2 text-sm">
                    <span className="h-3 w-3 rounded-full" style={{ backgroundColor: KIND_COLORS[key] || "#64748b" }} />
                    <span className="text-muted-foreground">{value}</span>
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
