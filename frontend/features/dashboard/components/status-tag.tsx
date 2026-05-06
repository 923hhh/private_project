"use client"

import { cn } from "@/shared/lib/utils"

interface StatusTagProps {
  status: "pending" | "processing" | "resolved" | "online" | "offline" | "maintenance"
  size?: "sm" | "md"
}

const statusConfig = {
  pending: {
    label: "待处理",
    bgColor: "bg-[#f59e0b]/10",
    textColor: "text-[#f59e0b]",
    dotColor: "bg-[#f59e0b]",
  },
  processing: {
    label: "处理中",
    bgColor: "bg-[#5e6ad2]/10",
    textColor: "text-[#5e6ad2]",
    dotColor: "bg-[#5e6ad2]",
  },
  resolved: {
    label: "已完成",
    bgColor: "bg-[#22c55e]/10",
    textColor: "text-[#22c55e]",
    dotColor: "bg-[#22c55e]",
  },
  online: {
    label: "在线",
    bgColor: "bg-[#22c55e]/10",
    textColor: "text-[#22c55e]",
    dotColor: "bg-[#22c55e]",
  },
  offline: {
    label: "离线",
    bgColor: "bg-[#8a8f98]/10",
    textColor: "text-[#8a8f98]",
    dotColor: "bg-[#8a8f98]",
  },
  maintenance: {
    label: "维护中",
    bgColor: "bg-[#f59e0b]/10",
    textColor: "text-[#f59e0b]",
    dotColor: "bg-[#f59e0b]",
  },
}

export function StatusTag({ status, size = "sm" }: StatusTagProps) {
  const config = statusConfig[status]
  
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full",
        config.bgColor,
        config.textColor,
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dotColor)} />
      {config.label}
    </span>
  )
}

interface SeverityTagProps {
  severity: "critical" | "warning" | "info"
  size?: "sm" | "md"
}

const severityConfig = {
  critical: {
    label: "严重",
    bgColor: "bg-[#ef4444]/10",
    textColor: "text-[#ef4444]",
  },
  warning: {
    label: "警告",
    bgColor: "bg-[#f59e0b]/10",
    textColor: "text-[#f59e0b]",
  },
  info: {
    label: "提示",
    bgColor: "bg-[#5e6ad2]/10",
    textColor: "text-[#5e6ad2]",
  },
}

export function SeverityTag({ severity, size = "sm" }: SeverityTagProps) {
  const config = severityConfig[severity]
  
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full",
        config.bgColor,
        config.textColor,
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm"
      )}
    >
      {config.label}
    </span>
  )
}

