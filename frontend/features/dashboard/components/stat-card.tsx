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
      value: "text-slate-800 dark:text-[#c6d4eb]",
      icon: "text-[#5d79a8] dark:text-[#8fa7cf]",
      iconBg: "border border-[#b8cae7] bg-[#eef4ff] dark:border-[#7c9ac9]/28 dark:bg-[#7c9ac9]/12",
      hoverBorder: "hover:border-[#9db6dd] dark:hover:border-[#7c9ac9]/35",
      hoverBg: "hover:bg-[#f5f9ff] dark:hover:bg-[#7c9ac9]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(124,154,201,0.12)]",
    },
    warning: {
      value: "text-[#c67b00] dark:text-[#fbbf24]",
      icon: "text-[#fbbf24]",
      iconBg: "border border-[#f3d18d] bg-[#fff7e8] dark:border-[#f59e0b]/28 dark:bg-[#f59e0b]/12",
      hoverBorder: "hover:border-[#e8bd62] dark:hover:border-[#f59e0b]/35",
      hoverBg: "hover:bg-[#fffaf1] dark:hover:bg-[#f59e0b]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(245,158,11,0.12)]",
    },
    critical: {
      value: "text-[#d9485f] dark:text-[#f87171]",
      icon: "text-[#f87171]",
      iconBg: "border border-[#f3b3bb] bg-[#fff1f3] dark:border-[#ef4444]/28 dark:bg-[#ef4444]/12",
      hoverBorder: "hover:border-[#ea98a5] dark:hover:border-[#ef4444]/35",
      hoverBg: "hover:bg-[#fff6f7] dark:hover:bg-[#ef4444]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(239,68,68,0.12)]",
    },
    success: {
      value: "text-[#15803d] dark:text-[#4ade80]",
      icon: "text-[#16a34a] dark:text-[#4ade80]",
      iconBg: "border border-[#9fddb5] bg-[#eefbf3] dark:border-[#22c55e]/28 dark:bg-[#22c55e]/12",
      hoverBorder: "hover:border-[#7ed39d] dark:hover:border-[#22c55e]/35",
      hoverBg: "hover:bg-[#f5fdf8] dark:hover:bg-[#22c55e]/[0.06]",
      iconGlow: "group-hover:shadow-[0_0_0_4px_rgba(34,197,94,0.12)]",
    },
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-[rgba(255,255,255,0.08)] dark:bg-[rgba(255,255,255,0.02)]">
        <div className="flex items-center justify-between">
          <div className="h-4 w-20 rounded bg-slate-100 skeleton-pulse dark:bg-[rgba(255,255,255,0.05)]" />
          <div className="h-8 w-8 rounded-lg bg-slate-100 skeleton-pulse dark:bg-[rgba(255,255,255,0.05)]" />
        </div>
        <div className="mt-3 h-8 w-24 rounded bg-slate-100 skeleton-pulse dark:bg-[rgba(255,255,255,0.05)]" />
        <div className="mt-2 h-3 w-16 rounded bg-slate-100 skeleton-pulse dark:bg-[rgba(255,255,255,0.05)]" />
      </div>
    )
  }

  return (
    <div
      className={cn(
        "group rounded-xl border border-slate-200 bg-white p-4 shadow-[0_6px_18px_rgba(15,23,42,0.04)] transition-[border-color,background-color] duration-200 dark:border-[rgba(255,255,255,0.08)] dark:bg-[rgba(255,255,255,0.02)] dark:shadow-none",
        statusStyles[status].hoverBorder,
        statusStyles[status].hoverBg
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-600 dark:text-[#8a8f98]">{title}</span>
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
        {unit && <span className="text-sm text-slate-500 dark:text-[#8a8f98]">{unit}</span>}
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
              change > 0 ? "text-[#16a34a] dark:text-[#22c55e]" : change < 0 ? "text-[#dc2626] dark:text-[#ef4444]" : "text-slate-500 dark:text-[#8a8f98]"
            )}
          >
            {Math.abs(change)}%
          </span>
          {changeLabel && <span className="text-xs text-slate-500 dark:text-[#8a8f98]">{changeLabel}</span>}
        </div>
      )}
    </div>
  )
}

