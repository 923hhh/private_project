"use client"

import { AlertCircle, Wrench, CheckCircle, Settings, Activity } from "lucide-react"
import { cn } from "@/shared/lib/utils"

interface TimelineEvent {
  id: string
  type: "fault" | "repair" | "resolved" | "maintenance" | "monitoring"
  title: string
  description?: string
  time: string
  operator?: string
}

interface TimelineProps {
  events: TimelineEvent[]
  loading?: boolean
  emptyState?: boolean
}

const eventConfig = {
  fault: {
    icon: AlertCircle,
    iconBg: "bg-[#ef4444]/10",
    iconColor: "text-[#ef4444]",
    lineColor: "bg-[#ef4444]/30",
  },
  repair: {
    icon: Wrench,
    iconBg: "bg-[#f59e0b]/10",
    iconColor: "text-[#f59e0b]",
    lineColor: "bg-[#f59e0b]/30",
  },
  resolved: {
    icon: CheckCircle,
    iconBg: "bg-[#22c55e]/10",
    iconColor: "text-[#22c55e]",
    lineColor: "bg-[#22c55e]/30",
  },
  maintenance: {
    icon: Settings,
    iconBg: "bg-[#5e6ad2]/10",
    iconColor: "text-[#5e6ad2]",
    lineColor: "bg-[#5e6ad2]/30",
  },
  monitoring: {
    icon: Activity,
    iconBg: "bg-[rgba(255,255,255,0.05)]",
    iconColor: "text-[#8a8f98]",
    lineColor: "bg-[rgba(255,255,255,0.08)]",
  },
}

export function Timeline({ events, loading = false, emptyState = false }: TimelineProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)]">
        <div className="border-b border-[rgba(255,255,255,0.05)] px-4 py-3">
          <div className="h-5 w-24 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
        </div>
        <div className="p-4 space-y-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex gap-3">
              <div className="h-8 w-8 rounded-full bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-40 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
                <div className="h-3 w-28 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (emptyState || events.length === 0) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)]">
        <div className="border-b border-[rgba(255,255,255,0.05)] px-4 py-3">
          <h3 className="text-sm font-medium text-[#f7f8f8]">诊断时间线</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-12">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[rgba(255,255,255,0.05)]">
            <Activity className="h-5 w-5 text-[#8a8f98]" />
          </div>
          <p className="mt-3 text-sm text-[#8a8f98]">暂无诊断记录</p>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)]">
      <div className="border-b border-[rgba(255,255,255,0.05)] px-4 py-3">
        <h3 className="text-sm font-medium text-[#f7f8f8]">诊断时间线</h3>
      </div>
      <div className="p-4">
        <div className="relative">
          {events.map((event, index) => {
            const config = eventConfig[event.type]
            const Icon = config.icon
            const isLast = index === events.length - 1

            return (
              <div key={event.id} className="relative flex gap-3 pb-6 last:pb-0">
                {/* Timeline line */}
                {!isLast && (
                  <div
                    className={cn(
                      "absolute left-4 top-8 w-px h-[calc(100%-8px)] -translate-x-1/2",
                      config.lineColor
                    )}
                  />
                )}
                
                {/* Icon */}
                <div className={cn("relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", config.iconBg)}>
                  <Icon className={cn("h-4 w-4", config.iconColor)} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[#f7f8f8]">{event.title}</p>
                  {event.description && (
                    <p className="mt-0.5 text-xs text-[#8a8f98] line-clamp-2">{event.description}</p>
                  )}
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-xs text-[#8a8f98]">{event.time}</span>
                    {event.operator && (
                      <>
                        <span className="text-xs text-[#8a8f98]/40">·</span>
                        <span className="text-xs text-[#8a8f98]">{event.operator}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

