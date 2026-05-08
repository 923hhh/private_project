export const DEMO_MODE_STORAGE_KEY = "faultdiag.demo_mode"
export const DEMO_MODE_CHANGED_EVENT = "faultdiag:demo-mode-changed"

function parseBooleanLike(value: string | null | undefined): boolean | null {
  if (!value) return null
  const v = value.trim().toLowerCase()
  if (["1", "true", "yes", "on"].includes(v)) return true
  if (["0", "false", "no", "off"].includes(v)) return false
  return null
}

/**
 * 演示模式开关。
 * - 优先读取环境变量 `NEXT_PUBLIC_DEMO_MODE`（便于比赛展示一键开启）
 * - 客户端可用 localStorage 覆盖（便于开发调试）
 */
export function isDemoMode(): boolean {
  const env = parseBooleanLike(process.env.NEXT_PUBLIC_DEMO_MODE)
  if (env !== null) return env

  if (typeof window === "undefined") return false
  try {
    const ls = parseBooleanLike(window.localStorage.getItem(DEMO_MODE_STORAGE_KEY))
    return ls ?? false
  } catch {
    return false
  }
}

export function setDemoMode(enabled: boolean) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(DEMO_MODE_STORAGE_KEY, enabled ? "1" : "0")
    window.dispatchEvent(
      new CustomEvent(DEMO_MODE_CHANGED_EVENT, {
        detail: { enabled },
      }),
    )
  } catch {
    // ignore
  }
}

