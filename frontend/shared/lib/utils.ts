import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * 将后端时间串规范为可被 Date 正确解析的形式。
 * SQLAlchemy / Python 常见 naive UTC（无时区后缀）在浏览器中会被当作本地时间解析，导致与真实 UTC 相差 8 小时等问题；
 * 此处对「含日期+时间且无 Z/偏移」的串按 UTC 解析（与后端 datetime.utcnow 一致）。
 */
function coerceBackendInstant(raw: string): string {
  const s = raw.trim()
  // 已带 Z 或常见 ±HH:MM / ±HHMM 偏移则不再追加
  if (/[zZ]$/i.test(s) || /[+-]\d{2}:\d{2}(:\d{2})?$/.test(s) || /[+-]\d{4}$/.test(s)) {
    return s
  }
  if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(s)) return s
  const t = s.includes('T') ? s : s.replace(' ', 'T')
  return t.endsWith('Z') ? t : `${t}Z`
}

function parseBackendDate(iso: string | null | undefined): Date | null {
  if (iso == null || iso === '') return null
  const d = new Date(coerceBackendInstant(String(iso)))
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * 将后端返回的 ISO 时间格式化为浏览器本地时区的 `YYYY-MM-DD HH:mm`。
 */
export function formatDateTimeLocal(iso: string | null | undefined): string {
  if (iso == null || iso === '') return '--'
  const d = parseBackendDate(iso)
  if (d == null) {
    return String(iso).replace('T', ' ').replace(/Z|[+-]\d{2}:?\d{2}$/, '').slice(0, 16)
  }
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${mo}-${day} ${h}:${min}`
}

/**
 * 根据起止时间计算经过时长（用于检修任务耗时等），输出中文短语。
 */
export function formatDurationBetween(
  start: string | null | undefined,
  end: string | null | undefined,
): string | null {
  const ds = parseBackendDate(start ?? undefined)
  const de = parseBackendDate(end ?? undefined)
  if (ds == null || de == null) return null
  let ms = de.getTime() - ds.getTime()
  if (ms < 0) ms = 0
  const secTotal = Math.floor(ms / 1000)
  if (secTotal === 0) return '不足 1 秒'
  if (secTotal < 60) return `${secTotal} 秒`
  const m = Math.floor(secTotal / 60)
  const s = secTotal % 60
  if (m < 60) return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分钟`
  const h = Math.floor(m / 60)
  const mm = m % 60
  return mm > 0 ? `${h} 小时 ${mm} 分` : `${h} 小时`
}
