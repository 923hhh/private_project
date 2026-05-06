"use client"

import { TrendingUp, TrendingDown } from "lucide-react"

interface MiniChartProps {
  data: number[]
  color?: string
  height?: number
}

export function MiniChart({ data, color = "#5e6ad2", height = 40 }: MiniChartProps) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1

  const points = data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * 100
      const y = 100 - ((value - min) / range) * 100
      return `${x},${y}`
    })
    .join(" ")

  const areaPoints = `0,100 ${points} 100,100`

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      className="w-full"
      style={{ height }}
    >
      <defs>
        <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={areaPoints}
        fill={`url(#gradient-${color})`}
      />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

interface TrendChartCardProps {
  title: string
  value: string | number
  unit?: string
  change?: number
  data: number[]
  color?: string
  loading?: boolean
}

export function TrendChartCard({
  title,
  value,
  unit,
  change,
  data,
  color = "#5e6ad2",
  loading = false,
}: TrendChartCardProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-4">
        <div className="h-4 w-24 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
        <div className="mt-3 flex items-end justify-between">
          <div className="space-y-2">
            <div className="h-7 w-20 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
            <div className="h-3 w-14 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
          </div>
          <div className="h-10 w-24 rounded bg-[rgba(255,255,255,0.05)] skeleton-pulse" />
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-4 transition-colors hover:border-[rgba(255,255,255,0.12)] hover:bg-[rgba(255,255,255,0.03)]">
      <span className="text-sm text-[#8a8f98]">{title}</span>
      <div className="mt-3 flex items-end justify-between">
        <div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-semibold text-[#f7f8f8]">{value}</span>
            {unit && <span className="text-sm text-[#8a8f98]">{unit}</span>}
          </div>
          {change !== undefined && (
            <div className="mt-1 flex items-center gap-1">
              {change >= 0 ? (
                <TrendingUp className="h-3 w-3 text-[#22c55e]" />
              ) : (
                <TrendingDown className="h-3 w-3 text-[#ef4444]" />
              )}
              <span
                className={`text-xs ${change >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}`}
              >
                {Math.abs(change)}%
              </span>
              <span className="text-xs text-[#8a8f98]">vs 上周</span>
            </div>
          )}
        </div>
        <div className="w-24">
          <MiniChart data={data} color={color} height={40} />
        </div>
      </div>
    </div>
  )
}

interface ProgressBarProps {
  value: number
  max?: number
  color?: string
  showLabel?: boolean
  size?: "sm" | "md"
}

export function ProgressBar({
  value,
  max = 100,
  color = "#5e6ad2",
  showLabel = false,
  size = "sm",
}: ProgressBarProps) {
  const percentage = Math.min((value / max) * 100, 100)

  return (
    <div className="flex items-center gap-2">
      <div
        className={`flex-1 overflow-hidden rounded-full bg-[rgba(255,255,255,0.05)] ${
          size === "sm" ? "h-1.5" : "h-2"
        }`}
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${percentage}%`, backgroundColor: color }}
        />
      </div>
      {showLabel && (
        <span className="text-xs text-[#8a8f98]">{Math.round(percentage)}%</span>
      )}
    </div>
  )
}

interface DonutChartProps {
  value: number
  max?: number
  size?: number
  strokeWidth?: number
  color?: string
  label?: string
}

export function DonutChart({
  value,
  max = 100,
  size = 80,
  strokeWidth = 8,
  color = "#5e6ad2",
  label,
}: DonutChartProps) {
  const percentage = Math.min((value / max) * 100, 100)
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-semibold text-[#f7f8f8]">{Math.round(percentage)}%</span>
        {label && <span className="text-[10px] text-[#8a8f98]">{label}</span>}
      </div>
    </div>
  )
}
