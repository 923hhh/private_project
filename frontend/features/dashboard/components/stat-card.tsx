"use client"

import { ArrowUp, ArrowDown, Minus } from "lucide-react"
import { cn } from "@/shared/lib/utils"

interface StatCardProps {
  title: string
  value: string | number
  unit?: string
  change?: number
  changeLabel?: string
  icon?: React.ReactNode
  status?: "normal" | "warning" | "critical" | "success"
  loading?: boolean
}

export function StatCard({
  title,
  value,
  unit,
  change,
  changeLabel,
  icon,
  status = "normal",
  loading = false,
}: StatCardProps) {
  const statusStyles = {
    normal: {
      value: "text-[#c6d4eb]",
      icon: "text-[#8fa7cf]",
      iconBg: "bg-[#7c9ac9]/12 border border-[#7c9ac9]/28",
      hoverBorder: "hover:border-[#7c9ac9]/35",
      hoverBg: "hover:bg-[#7c9ac9]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(124,154,201,0.12)]",
    },
    warning: {
      value: "text-[#fbbf24]",
      icon: "text-[#fbbf24]",
      iconBg: "bg-[#f59e0b]/12 border border-[#f59e0b]/28",
      hoverBorder: "hover:border-[#f59e0b]/35",
      hoverBg: "hover:bg-[#f59e0b]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(245,158,11,0.12)]",
    },
    critical: {
      value: "text-[#f87171]",
      icon: "text-[#f87171]",
      iconBg: "bg-[#ef4444]/12 border border-[#ef4444]/28",
      hoverBorder: "hover:border-[#ef4444]/35",
      hoverBg: "hover:bg-[#ef4444]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(239,68,68,0.12)]",
    },
    success: {
      value: "text-[#4ade80]",
      icon: "text-[#4ade80]",
      iconBg: "bg-[#22c55e]/12 border border-[#22c55e]/28",
      hoverBorder: "hover:border-[#22c55e]/35",
      hoverBg: "hover:bg-[#22c55e]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(34,197,94,0.12)]",
    },
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-4">
        <div className="flex items-center justify-between">
          <div className="h-4 w-20 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
          <div className="h-8 w-8 rounded-lg bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
        </div>
        <div className="mt-3 h-8 w-24 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
        <div className="mt-2 h-3 w-16 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
      </div>
    )
  }

  return (
    <div
      className={cn(
        "group rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-4 transition-[border-color,background-color] duration-200",
        statusStyles[status].hoverBorder,
        statusStyles[status].hoverBg
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-[#8a8f98]">{title}</span>
        {icon && (
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg transition-shadow duration-200",
              statusStyles[status].iconBg,
              statusStyles[status].iconGlow
            )}
          >
            <span className={statusStyles[status].icon}>{icon}</span>
          </div>
        )}
      </div>
      
      <div className="mt-3 flex items-baseline gap-1">
        <span className={cn("text-2xl font-semibold", statusStyles[status].value)}>{value}</span>
        {unit && <span className="text-sm text-[#8a8f98]">{unit}</span>}
      </div>

      {change !== undefined && (
        <div className="mt-2 flex items-center gap-1.5">
          {change > 0 ? (
            <ArrowUp className="h-3 w-3 text-[#22c55e]" />
          ) : change < 0 ? (
            <ArrowDown className="h-3 w-3 text-[#ef4444]" />
          ) : (
            <Minus className="h-3 w-3 text-[#8a8f98]" />
          )}
          <span
            className={cn(
              "text-xs",
              change > 0 ? "text-[#22c55e]" : change < 0 ? "text-[#ef4444]" : "text-[#8a8f98]"
            )}
          >
            {Math.abs(change)}%
          </span>
          {changeLabel && <span className="text-xs text-[#8a8f98]">{changeLabel}</span>}
        </div>
      )}
    </div>
  )
}

