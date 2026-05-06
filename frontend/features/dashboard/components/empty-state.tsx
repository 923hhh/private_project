"use client"

import { AlertTriangle, Database, Server, Activity, FileX, Inbox } from "lucide-react"
import { Button } from "@/shared/components/ui/button"
import { cn } from "@/shared/lib/utils"

type EmptyStateType = "no-data" | "no-devices" | "no-faults" | "no-results" | "error" | "offline"

interface EmptyStateProps {
  type?: EmptyStateType
  title?: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
  className?: string
}

const emptyStateConfig = {
  "no-data": {
    icon: Database,
    title: "暂无数据",
    description: "当前没有可显示的数据",
  },
  "no-devices": {
    icon: Server,
    title: "暂无设备",
    description: "请添加设备开始监控",
  },
  "no-faults": {
    icon: Activity,
    title: "暂无故障记录",
    description: "所有设备运行正常",
  },
  "no-results": {
    icon: FileX,
    title: "无搜索结果",
    description: "尝试调整搜索条件",
  },
  "error": {
    icon: AlertTriangle,
    title: "加载失败",
    description: "数据获取出错，请稍后重试",
  },
  "offline": {
    icon: Inbox,
    title: "网络离线",
    description: "请检查网络连接后重试",
  },
}

export function EmptyState({
  type = "no-data",
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  const config = emptyStateConfig[type]
  const Icon = config.icon

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] py-16 px-4",
        className
      )}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[rgba(255,255,255,0.05)]">
        <Icon className={cn(
          "h-7 w-7",
          type === "error" ? "text-[#ef4444]" : "text-[#8a8f98]"
        )} />
      </div>
      <p className="mt-4 text-sm font-medium text-[#d0d6e0]">
        {title || config.title}
      </p>
      <p className="mt-1 text-center text-xs text-[#8a8f98]">
        {description || config.description}
      </p>
      {action && (
        <Button
          onClick={action.onClick}
          className="mt-4 h-8 bg-[#5e6ad2] px-4 text-xs text-white hover:bg-[#7170ff]"
        >
          {action.label}
        </Button>
      )}
    </div>
  )
}

interface ErrorStateProps {
  title?: string
  description?: string
  onRetry?: () => void
}

export function ErrorState({
  title = "加载失败",
  description = "数据获取出错，请稍后重试",
  onRetry,
}: ErrorStateProps) {
  return (
    <EmptyState
      type="error"
      title={title}
      description={description}
      action={onRetry ? { label: "重新加载", onClick: onRetry } : undefined}
    />
  )
}

