"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { maintenanceLogin } from "@/features/auth/api"
import { ROUTES } from "@/shared/lib/routes"
import { setMaintenanceToken } from "@/features/auth/lib/token-store"
import {
  Eye,
  EyeOff,
  Lock,
  User,
  ShieldCheck,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  KeyRound,
} from "lucide-react"

// 输入框组件
function InputField({
  id,
  label,
  type,
  value,
  onChange,
  placeholder,
  icon: Icon,
  error,
  autoComplete,
  showToggle,
  onToggle,
  showPassword,
}: {
  id: string
  label: string
  type: string
  value: string
  onChange: (value: string) => void
  placeholder: string
  icon: React.ElementType
  error?: string
  autoComplete?: string
  showToggle?: boolean
  onToggle?: () => void
  showPassword?: boolean
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-primary">
        {label}
      </label>
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
          <Icon className="h-4 w-4 text-slate-500 dark:text-tertiary" />
        </div>
        <input
          id={id}
          type={showToggle ? (showPassword ? "text" : "password") : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className={`
            block w-full rounded-md border bg-slate-100/90 py-2.5 pl-10 pr-10
            text-sm text-slate-900 placeholder:text-slate-500
            transition-all duration-200
            focus:border-brand focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand/50
            dark:bg-[rgba(255,255,255,0.02)] dark:text-primary dark:placeholder:text-tertiary dark:focus:bg-[rgba(255,255,255,0.04)]
            ${error ? "border-red-500/50" : "border-border"}
          `}
        />
        {showToggle && (
          <button
            type="button"
            onClick={onToggle}
            className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-500 transition-colors hover:text-slate-800 dark:text-tertiary dark:hover:text-secondary"
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>
      {error && (
        <p className="flex items-center gap-1.5 text-xs text-red-400">
          <AlertCircle className="h-3 w-3" />
          {error}
        </p>
      )}
    </div>
  )
}

// 错误提示Banner
function ErrorBanner({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
      <div className="flex-1">
        <p className="text-sm text-red-300">{message}</p>
      </div>
      <button
        onClick={onDismiss}
        className="text-red-400 transition-colors hover:text-red-300"
        aria-label="关闭提示"
      >
        <XCircle className="h-4 w-4" />
      </button>
    </div>
  )
}

// 成功提示Banner
function SuccessBanner({ message }: { message: string }) {
  return (
    <div className="mb-4 flex flex-col gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
        <p className="text-sm text-emerald-300">{message}</p>
      </div>
      <Link
        href={ROUTES.dashboard}
        className="shrink-0 text-sm font-medium text-emerald-200 underline-offset-4 hover:text-emerald-100 hover:underline"
      >
        进入工作台 →
      </Link>
    </div>
  )
}

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    username?: string
    password?: string
  }>({})
  const [nextPath, setNextPath] = useState<string>(ROUTES.dashboard)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const rawNext = params.get("next")?.trim()
    if (rawNext && rawNext.startsWith("/")) {
      setNextPath(rawNext)
    }
    if (params.get("reason") === "expired") {
      setError("登录已失效，请重新登录")
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setFieldErrors({})

    // 验证
    const errors: typeof fieldErrors = {}
    if (!username) errors.username = "请输入账号"
    if (!password) errors.password = "请输入密码"

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }

    setIsLoading(true)

    try {
      const data = await maintenanceLogin(username, password)
      setMaintenanceToken(data.access_token, rememberMe)
      setSuccess(rememberMe ? "登录成功，已记住当前登录状态" : "登录成功，当前会话已保持登录")
      router.push(nextPath)
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-12">
      {/* 背景装饰 */}
      <div className="pointer-events-none absolute inset-0">
        {/* 渐变背景 */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(94,106,210,0.08),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(113,112,255,0.05),transparent_50%)]" />
        {/* 噪点纹理 */}
        <div
          className="absolute inset-0 opacity-[0.015]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          }}
        />
        {/* 网格线 */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)`,
            backgroundSize: "60px 60px",
          }}
        />
      </div>

      {/* 登录卡片 */}
      <div className="relative z-10 w-full max-w-md">
        {/* 返回主站链接 */}
        <Link
          href="/"
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 text-sm text-slate-700 backdrop-blur-sm transition-colors hover:border-slate-300 hover:bg-white hover:text-slate-900 dark:border-white/[0.10] dark:bg-panel/35 dark:text-[#9fb0c5] dark:hover:border-white/[0.22] dark:hover:bg-white/[0.08] dark:hover:text-[#f5f7fa]"
        >
          <ArrowLeft className="h-4 w-4" />
          返回主站
        </Link>

        {/* 主卡片 */}
        <div className="rounded-xl border border-border bg-panel/80 p-6 shadow-2xl backdrop-blur-sm sm:p-8">
          {/* Logo和标题 */}
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-slate-200 bg-white/90 dark:border-border dark:bg-[rgba(255,255,255,0.03)]">
              <KeyRound className="h-7 w-7 text-brand" />
            </div>
            <h1 className="text-xl font-semibold text-brand dark:text-primary">运维管理后台</h1>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">请使用您的账号登录系统</p>
          </div>

          {/* 错误/成功提示 */}
          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
          {success && <SuccessBanner message={success} />}

          {/* 登录表单 */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <InputField
              id="username"
              label="账号"
              type="text"
              value={username}
              onChange={setUsername}
              placeholder="请输入账号"
              icon={User}
              error={fieldErrors.username}
              autoComplete="username"
            />

            <InputField
              id="password"
              label="密码"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="请输入密码"
              icon={Lock}
              error={fieldErrors.password}
              autoComplete="current-password"
              showToggle
              onToggle={() => setShowPassword(!showPassword)}
              showPassword={showPassword}
            />

            {/* 记住我和忘记密码 */}
            <div className="flex items-center justify-between">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 rounded border border-border bg-card text-brand focus:ring-1 focus:ring-brand/50 focus:ring-offset-0"
                />
                <span className="text-sm text-slate-700 dark:text-slate-200">记住登录状态</span>
              </label>
              <Link
                href="/login"
                className="text-sm text-brand-dark transition-colors hover:text-brand dark:text-brand dark:hover:text-brand-light"
              >
                忘记密码？
              </Link>
            </div>

            {/* 登录按钮 */}
            <button
              type="submit"
              disabled={isLoading}
              className="
                relative mt-6 flex w-full items-center justify-center gap-2 rounded-md
                bg-brand px-4 py-2.5 text-sm font-medium text-white
                shadow-lg shadow-brand/20
                transition-all duration-200
                hover:bg-brand-light hover:shadow-brand/30
                focus:outline-none focus:ring-2 focus:ring-brand/50 focus:ring-offset-2 focus:ring-offset-background
                disabled:cursor-not-allowed disabled:opacity-60
              "
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在登录...
                </>
              ) : (
                <>
                  <Lock className="h-4 w-4" />
                  安全登录
                </>
              )}
            </button>
          </form>

          {/* 安全提示 */}
          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-600 dark:text-slate-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>连接已加密，您的信息受到保护</span>
          </div>
        </div>

        {/* 版权信息 */}
        <p className="mt-6 text-center text-xs text-slate-700 dark:text-slate-400">
          &copy; 2024 工业故障诊断平台 · v2.1.0
        </p>
      </div>
    </div>
  )
}

