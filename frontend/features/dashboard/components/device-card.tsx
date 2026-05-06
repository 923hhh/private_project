"use client"

import { Server, Cpu, HardDrive, Gauge } from "lucide-react"
import { StatusTag } from "./status-tag"
import { cn } from "@/shared/lib/utils"

interface DeviceCardProps {
  name: string
  code: string
  type: string
  status: "online" | "offline" | "maintenance"
  metrics?: {
    cpu?: number
    memory?: number
    temperature?: number
  }
  loading?: boolean
}

export function DeviceCard({ name, code, type, status, metrics, loading = false }: DeviceCardProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
            <div className="space-y-2">
              <div className="h-4 w-28 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
              <div className="h-3 w-20 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
            </div>
          </div>
          <div className="h-5 w-12 rounded-full bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 w-8 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
              <div className="h-5 w-12 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="group rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-4 transition-all hover:border-[rgba(255,255,255,0.12)] hover:bg-[rgba(255,255,255,0.03)]">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(255,255,255,0.05)]">
            <Server className="h-5 w-5 text-[#5e6ad2]" />
          </div>
          <div>
            <p className="text-sm font-medium text-[#f7f8f8]">{name}</p>
            <p className="text-xs text-[#8a8f98]">{code} · {type}</p>
          </div>
        </div>
        <StatusTag status={status} />
      </div>

      {metrics && (
        <div className="mt-4 grid grid-cols-3 gap-4">
          {metrics.cpu !== undefined && (
            <MetricItem
              icon={<Cpu className="h-3.5 w-3.5" />}
              label="CPU"
              value={`${metrics.cpu}%`}
              status={metrics.cpu > 80 ? "critical" : metrics.cpu > 60 ? "warning" : "normal"}
            />
          )}
          {metrics.memory !== undefined && (
            <MetricItem
              icon={<HardDrive className="h-3.5 w-3.5" />}
              label="内存"
              value={`${metrics.memory}%`}
              status={metrics.memory > 80 ? "critical" : metrics.memory > 60 ? "warning" : "normal"}
            />
          )}
          {metrics.temperature !== undefined && (
            <MetricItem
              icon={<Gauge className="h-3.5 w-3.5" />}
              label="温度"
              value={`${metrics.temperature}°C`}
              status={metrics.temperature > 80 ? "critical" : metrics.temperature > 60 ? "warning" : "normal"}
            />
          )}
        </div>
      )}
    </div>
  )
}

interface MetricItemProps {
  icon: React.ReactNode
  label: string
  value: string
  status: "normal" | "warning" | "critical"
}

function MetricItem({ icon, label, value, status }: MetricItemProps) {
  const statusColors = {
    normal: "text-[#d0d6e0]",
    warning: "text-[#f59e0b]",
    critical: "text-[#ef4444]",
  }

  return (
    <div>
      <div className="flex items-center gap-1 text-[#8a8f98]">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p className={cn("mt-0.5 text-sm font-medium", statusColors[status])}>{value}</p>
    </div>
  )
}

interface DeviceGridProps {
  devices: Array<{
    id: string
    name: string
    code: string
    type: string
    status: "online" | "offline" | "maintenance"
    metrics?: {
      cpu?: number
      memory?: number
      temperature?: number
    }
  }>
  loading?: boolean
  emptyState?: boolean
}

export function DeviceGrid({ devices, loading = false, emptyState = false }: DeviceGridProps) {
  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(6)].map((_, i) => (
          <DeviceCard
            key={i}
            name=""
            code=""
            type=""
            status="online"
            loading={true}
          />
        ))}
      </div>
    )
  }

  if (emptyState || devices.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] py-16">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(255,255,255,0.05)]">
          <Server className="h-6 w-6 text-[#8a8f98]" />
        </div>
        <p className="mt-4 text-sm text-[#8a8f98]">暂无设备数据</p>
        <p className="mt-1 text-xs text-[#8a8f98]/60">请添加设备开始监控</p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {devices.map((device) => (
        <DeviceCard
          key={device.id}
          name={device.name}
          code={device.code}
          type={device.type}
          status={device.status}
          metrics={device.metrics}
        />
      ))}
    </div>
  )
}

