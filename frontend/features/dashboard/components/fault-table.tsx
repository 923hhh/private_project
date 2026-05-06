"use client"

import { MoreHorizontal, AlertTriangle, AlertCircle, Info, ChevronRight } from "lucide-react"
import { Button } from "@/shared/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu"
import { StatusTag } from "./status-tag"

export interface FaultRecord {
  id: string
  deviceName: string
  deviceCode: string
  faultType: string
  severity: "critical" | "warning" | "info"
  status: "pending" | "processing" | "resolved"
  time: string
  operator?: string
}

interface FaultTableProps {
  data: FaultRecord[]
  loading?: boolean
  emptyState?: boolean
  /** 点击「查看全部」时触发（例如拉取监控指标或跳转前校验后端） */
  onViewAll?: () => void | Promise<void>
  /** 行菜单：查看详情 / 处理故障 / 导出记录 / 删除记录 */
  onMenuAction?: (
    action: "detail" | "process" | "export" | "delete",
    record: FaultRecord,
  ) => void | Promise<void>
}

const severityIcons = {
  critical: <AlertCircle className="h-4 w-4" />,
  warning: <AlertTriangle className="h-4 w-4" />,
  info: <Info className="h-4 w-4" />,
}

const severityColors = {
  critical: "text-[#ef4444]",
  warning: "text-[#f59e0b]",
  info: "text-[#5e6ad2]",
}

const severityLabels = {
  critical: "严重",
  warning: "警告",
  info: "提示",
}

export function FaultTable({
  data,
  loading = false,
  emptyState = false,
  onViewAll,
  onMenuAction,
}: FaultTableProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)]">
        <div className="border-b border-[rgba(255,255,255,0.05)] px-4 py-3">
          <div className="h-5 w-32 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
        </div>
        <div className="divide-y divide-[rgba(255,255,255,0.05)]">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-3">
              <div className="h-4 w-4 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-48 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
                <div className="h-3 w-32 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
              </div>
              <div className="h-6 w-16 rounded-full bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (emptyState || data.length === 0) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)]">
        <div className="border-b border-[rgba(255,255,255,0.05)] px-4 py-3">
          <h3 className="text-sm font-medium text-[#f7f8f8]">故障记录</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-16">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(255,255,255,0.05)]">
            <AlertTriangle className="h-6 w-6 text-[#8a8f98]" />
          </div>
          <p className="mt-4 text-sm text-[#8a8f98]">暂无故障记录</p>
          <p className="mt-1 text-xs text-[#8a8f98]/60">所有设备运行正常</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)]">
      <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.05)] px-4 py-3">
        <h3 className="text-sm font-medium text-[#f7f8f8]">故障记录</h3>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 text-xs text-[#5e6ad2] hover:bg-[rgba(94,106,210,0.1)] hover:text-[#7170ff]"
          onClick={() => void onViewAll?.()}
        >
          查看全部
          <ChevronRight className="h-3 w-3" />
        </Button>
      </div>
      
      {/* Table Body */}
      <div className="divide-y divide-[rgba(255,255,255,0.05)]">
        {data.map((record) => (
          <div
            key={record.id}
            className="group flex flex-col gap-3 px-4 py-3 transition-colors hover:bg-[rgba(255,255,255,0.02)] md:grid md:grid-cols-[1fr,120px,100px,100px,140px,40px] md:items-center md:gap-4"
          >
            {/* Device Info */}
            <div className="flex items-center gap-3">
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-[rgba(255,255,255,0.05)] ${severityColors[record.severity]}`}>
                {severityIcons[record.severity]}
              </div>
              <div>
                <p className="text-sm font-medium text-[#f7f8f8]">{record.deviceName}</p>
                <p className="text-xs text-[#8a8f98]">{record.deviceCode}</p>
              </div>
            </div>

            {/* Mobile Layout Info */}
            <div className="flex flex-wrap gap-2 md:hidden">
              <span className="text-xs text-[#8a8f98]">{record.faultType}</span>
              <span className="text-xs text-[#8a8f98]">|</span>
              <span className={`text-xs ${severityColors[record.severity]}`}>{severityLabels[record.severity]}</span>
              <span className="text-xs text-[#8a8f98]">|</span>
              <StatusTag status={record.status} />
              <span className="text-xs text-[#8a8f98]">|</span>
              <span className="text-xs text-[#8a8f98]">{record.time}</span>
            </div>

            {/* Desktop Columns */}
            <span className="hidden text-sm text-[#d0d6e0] md:block">{record.faultType}</span>
            <span className={`hidden text-sm md:block ${severityColors[record.severity]}`}>
              {severityLabels[record.severity]}
            </span>
            <div className="hidden md:block">
              <StatusTag status={record.status} />
            </div>
            <span className="hidden text-sm text-[#8a8f98] md:block">{record.time}</span>
            
            {/* Actions：移动端与桌面端均可用 */}
            <div className="flex justify-end md:justify-end">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-[#8a8f98] opacity-100 hover:bg-[rgba(255,255,255,0.05)] md:opacity-0 md:group-hover:opacity-100"
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-36 border-[rgba(255,255,255,0.08)] bg-[#0f1011]">
                  <DropdownMenuItem
                    className="text-[#d0d6e0] focus:bg-[rgba(255,255,255,0.05)] focus:text-[#f7f8f8]"
                    onClick={() => void onMenuAction?.("detail", record)}
                  >
                    查看详情
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-[#d0d6e0] focus:bg-[rgba(255,255,255,0.05)] focus:text-[#f7f8f8]"
                    onClick={() => void onMenuAction?.("process", record)}
                  >
                    处理故障
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-[#d0d6e0] focus:bg-[rgba(255,255,255,0.05)] focus:text-[#f7f8f8]"
                    onClick={() => void onMenuAction?.("export", record)}
                  >
                    导出记录
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-red-400 focus:bg-red-500/10 focus:text-red-300"
                    onClick={() => void onMenuAction?.("delete", record)}
                  >
                    删除记录
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

