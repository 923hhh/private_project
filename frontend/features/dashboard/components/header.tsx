"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Bell, Search, Settings, HelpCircle, ChevronDown, Menu, LogIn, LogOut, ShieldCheck, Server, Wrench } from "lucide-react"
import { pingBackendReadiness, fetchHealth, fetchMaintenanceHealth, getApiBase } from "@/features/dashboard/api"
import { AppLogoLink } from "@/shared/components/brand/app-logo-link"
import { ROUTES } from "@/shared/lib/routes"
import {
  clearMaintenanceToken,
  getMaintenanceToken,
  MAINTENANCE_AUTH_EXPIRED_EVENT,
} from "@/features/auth/lib/token-store"
import { Button } from "@/shared/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/components/ui/avatar"
import { Input } from "@/shared/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/shared/components/ui/sheet"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu"
import { toast } from "sonner"

type NotificationItem = {
  id: number
  title: string
  detail: string
  read: boolean
}

const dashboardNavItems = [
  { label: "主页", href: ROUTES.marketingHome },
  { label: "检修总览", href: ROUTES.dashboard },
  { label: "智能诊断", href: "/tasks" },
  { label: "检修工单", href: "/tickets" },
  { label: "知识案例库", href: "/cases" },
] as const

const knowledgeSubItems = [
  { label: "知识文档管理", href: "/knowledge" },
  { label: "知识图谱", href: "/knowledge/graph" },
] as const

const marketingNavItem = { label: "产品官网", href: ROUTES.marketingHome } as const

export function Header() {
  const router = useRouter()
  const pathname = usePathname()
  const headerRef = useRef<HTMLElement | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState("")
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [healthStatus, setHealthStatus] = useState<string>("未检查")
  const [maintenanceStatus, setMaintenanceStatus] = useState<string>("未检查")
  const [readinessStatus, setReadinessStatus] = useState<string>("未检查")
  const [notifications, setNotifications] = useState<NotificationItem[]>([
    { id: 1, title: "工单超时预警", detail: "TK-2024-0891 还有 28 分钟超时", read: false },
    { id: 2, title: "诊断任务完成", detail: "TSK-2024-0234 已生成诊断结论", read: false },
    { id: 3, title: "新案例待审核", detail: "CASE-018 已提交待审核", read: true },
  ])
  const unreadCount = notifications.filter((item) => !item.read).length
  const searchPool = useMemo(() => [...dashboardNavItems, ...knowledgeSubItems, marketingNavItem], [])
  const searchResults = useMemo(() => {
    const q = searchKeyword.trim().toLowerCase()
    if (!q) return searchPool
    return searchPool.filter((item) => item.label.toLowerCase().includes(q) || item.href.toLowerCase().includes(q))
  }, [searchPool, searchKeyword])

  useEffect(() => {
    setIsLoggedIn(Boolean(getMaintenanceToken()))
  }, [pathname])

  useEffect(() => {
    const handleExpired = () => {
      setIsLoggedIn(false)
    }
    window.addEventListener(MAINTENANCE_AUTH_EXPIRED_EVENT, handleExpired as EventListener)
    return () => {
      window.removeEventListener(MAINTENANCE_AUTH_EXPIRED_EVENT, handleExpired as EventListener)
    }
  }, [])

  const handleLogout = () => {
    clearMaintenanceToken()
    setIsLoggedIn(false)
    setSettingsOpen(false)
    toast.success("已退出登录")
    router.push(ROUTES.login)
    router.refresh()
  }

  const handleOpenLogin = () => {
    setSettingsOpen(false)
    router.push(ROUTES.login)
  }

  const runHealthCheck = async () => {
    try {
      const data = await fetchHealth()
      const status = `${data.status} / DB ${data.database}`
      setHealthStatus(status)
      toast.success("系统健康检查完成")
    } catch (e) {
      const message = e instanceof Error ? e.message : "检查失败"
      setHealthStatus(`失败：${message}`)
      toast.error(message)
    }
  }

  const runMaintenanceCheck = async () => {
    try {
      const data = await fetchMaintenanceHealth()
      const status = typeof data?.status === "string" ? data.status : "连通正常"
      setMaintenanceStatus(status)
      toast.success("检修域连通检查完成")
    } catch (e) {
      const message = e instanceof Error ? e.message : "检查失败"
      setMaintenanceStatus(`失败：${message}`)
      toast.error(message)
    }
  }

  const runReadinessCheck = async () => {
    try {
      await pingBackendReadiness()
      setReadinessStatus("后端已就绪")
      toast.success("后端就绪检查完成")
    } catch (e) {
      const message = e instanceof Error ? e.message : "检查失败"
      setReadinessStatus(`失败：${message}`)
      toast.error(message)
    }
  }

  return (
    <>
      {/* 占位：Header 固定在视口顶部，避免遮挡页面内容 */}
      <div className="h-[72px]" aria-hidden="true" />
      <header ref={headerRef as unknown as React.RefObject<HTMLElement>} className="fixed left-0 right-0 top-0 z-50 w-full border-b border-border/70 bg-background/98 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/95">
        <div className="mx-auto flex h-[72px] max-w-[1200px] items-center justify-between px-4 lg:px-6">
        {/* Logo & Nav */}
        <div className="flex items-center gap-6">
          {/* Mobile menu */}
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="md:hidden h-9 w-9 text-foreground/85 hover:bg-accent hover:text-foreground"
                aria-label="打开菜单"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="border-border">
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-emerald-600 text-white text-xs font-semibold">
                    FD
                  </span>
                  <span>导航</span>
                </SheetTitle>
              </SheetHeader>
              <div className="px-4 pb-4 space-y-2">
                {dashboardNavItems.map((item) => {
                  const active = item.href === ROUTES.marketingHome
                    ? pathname === ROUTES.marketingHome
                    : pathname?.startsWith(item.href) ?? false
                  const isKnowledgeMenu = item.href === "/cases"
                  return (
                    <div key={item.href} className="space-y-2">
                      <button
                        type="button"
                        className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                          active
                            ? "border-emerald-500/30 bg-emerald-500/10 text-foreground"
                            : "border-border bg-background text-muted-foreground hover:bg-accent hover:text-foreground"
                        }`}
                        onClick={() => {
                          setMobileNavOpen(false)
                          router.push(item.href)
                        }}
                      >
                        {item.label}
                      </button>
                      {isKnowledgeMenu ? (
                        <div className="ml-3 space-y-2 border-l border-border pl-3">
                          {knowledgeSubItems.map((subItem) => {
                            const subActive = pathname?.startsWith(subItem.href) ?? false
                            return (
                              <button
                                key={subItem.href}
                                type="button"
                                className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                                  subActive
                                    ? "border-emerald-500/30 bg-emerald-500/10 text-foreground"
                                    : "border-border bg-background text-muted-foreground hover:bg-accent hover:text-foreground"
                                }`}
                                onClick={() => {
                                  setMobileNavOpen(false)
                                  router.push(subItem.href)
                                }}
                              >
                                {subItem.label}
                              </button>
                            )
                          })}
                        </div>
                      ) : null}
                    </div>
                  )
                })}

                <div className="mt-4 rounded-lg border border-border bg-background p-3">
                  <div className="text-xs text-muted-foreground">快捷入口</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                      onClick={() => {
                        setMobileNavOpen(false)
                        router.push(ROUTES.marketingHome)
                      }}
                    >
                      产品官网
                    </button>
                    <button
                      type="button"
                      className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                      onClick={() => {
                        setMobileNavOpen(false)
                        setSearchOpen(true)
                      }}
                    >
                      全局搜索
                    </button>
                  </div>
                </div>
              </div>
            </SheetContent>
          </Sheet>

          <AppLogoLink href={ROUTES.marketingHome} title="返回产品官网" />
          
          <nav className="hidden items-center gap-1 md:flex">
            {dashboardNavItems.map((item) => {
              const active = item.href === ROUTES.marketingHome
                ? pathname === ROUTES.marketingHome
                : pathname?.startsWith(item.href) ?? false

              if (item.href !== "/cases") {
                return (
                  <NavItem key={item.href} href={item.href} active={active}>
                    {item.label}
                  </NavItem>
                )
              }

              const menuActive = active || knowledgeSubItems.some((subItem) => pathname?.startsWith(subItem.href) ?? false)
              return (
                <div key={item.href} className="group relative">
                  <div
                    className={`inline-flex items-center rounded-md text-sm font-medium transition-colors ${
                      menuActive
                        ? "bg-accent text-foreground"
                        : "text-muted-foreground hover:bg-accent/70 hover:text-foreground"
                    }`}
                  >
                    <Link href={item.href} className="px-3 py-1.5">
                      {item.label}
                    </Link>
                    <span className="pr-2">
                      <ChevronDown className="h-3.5 w-3.5" />
                    </span>
                  </div>
                  <div className="pointer-events-none absolute left-0 top-full z-50 pt-2 opacity-0 transition-all duration-150 group-hover:pointer-events-auto group-hover:opacity-100">
                    <div className="w-44 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md">
                      {knowledgeSubItems.map((subItem) => (
                        <Link
                          key={subItem.href}
                          href={subItem.href}
                          className="flex rounded-sm px-2 py-1.5 text-sm text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                        >
                          {subItem.label}
                        </Link>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })}
          </nav>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-foreground/80 hover:bg-accent hover:text-foreground"
            onClick={() => {
              setSearchOpen(true)
            }}
          >
            <Search className="h-4 w-4" />
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="relative h-8 w-8 text-foreground/80 hover:bg-accent hover:text-foreground"
              >
                <Bell className="h-4 w-4" />
                {unreadCount > 0 ? <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-[#ef4444]" /> : null}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80 border-border bg-popover p-1 text-popover-foreground">
              <div className="px-2 py-1.5 text-xs text-muted-foreground">通知中心</div>
              {notifications.map((item) => (
                <DropdownMenuItem
                  key={item.id}
                  className="flex flex-col items-start gap-0.5 rounded-md px-2 py-2 text-foreground focus:bg-accent focus:text-accent-foreground"
                  onClick={() => {
                    setNotifications((prev) => prev.map((n) => (n.id === item.id ? { ...n, read: true } : n)))
                  }}
                >
                  <div className="flex w-full items-center justify-between">
                    <span className="text-sm">{item.title}</span>
                    {!item.read ? <span className="h-2 w-2 rounded-full bg-[#ef4444]" /> : null}
                  </div>
                  <span className="text-xs text-muted-foreground">{item.detail}</span>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator className="bg-border" />
              <DropdownMenuItem
                className="text-center text-xs text-muted-foreground focus:bg-accent"
                onClick={() => {
                  setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
                }}
              >
                全部标为已读
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-foreground/80 hover:bg-accent hover:text-foreground"
              >
                <HelpCircle className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44 border-border bg-popover text-popover-foreground">
              <DropdownMenuItem asChild>
                <Link
                  href={ROUTES.marketingHome}
                  className="cursor-pointer text-foreground focus:bg-accent focus:text-accent-foreground"
                >
                  返回产品官网
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-border" />
              <DropdownMenuItem
                className="text-foreground focus:bg-accent focus:text-accent-foreground"
                onClick={() => {
                  window.open(`${getApiBase()}/docs`, "_blank", "noopener,noreferrer")
                }}
              >
                接口文档
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-foreground focus:bg-accent focus:text-accent-foreground"
                onClick={() => {
                  void fetchHealth()
                }}
              >
                系统健康检查
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-foreground focus:bg-accent focus:text-accent-foreground"
                onClick={() => {
                  void fetchMaintenanceHealth()
                }}
              >
                检修域连通检查
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="mx-2 h-5 w-px bg-border" />

          {isLoggedIn ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-8 gap-2 px-2 hover:bg-accent">
                  <Avatar className="h-6 w-6">
                    <AvatarImage src="/placeholder-user.jpg" />
                    <AvatarFallback className="bg-[#5e6ad2] text-xs text-white">管</AvatarFallback>
                  </Avatar>
                  <span className="hidden text-sm text-foreground lg:inline-block">管理员</span>
                  <ChevronDown className="h-3 w-3 text-foreground/70" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44 border-border bg-popover text-popover-foreground">
                <DropdownMenuItem
                  className="text-foreground focus:bg-accent focus:text-accent-foreground"
                  onClick={handleLogout}
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button
              type="button"
              variant="ghost"
              className="h-8 gap-2 px-3 text-foreground hover:bg-accent"
              onClick={handleOpenLogin}
            >
              <LogIn className="h-4 w-4" />
              <span className="text-sm">前往登录</span>
            </Button>
          )}

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-foreground/80 hover:bg-accent hover:text-foreground"
            onClick={() => {
              setSettingsOpen(true)
            }}
            aria-label="系统设置"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
        </div>
      </header>

      <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
        <DialogContent className="border-border bg-popover text-popover-foreground sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>全局搜索</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              autoFocus
              value={searchKeyword}
              placeholder="输入页面名称，例如：工单 / 案例 / 监控"
              onChange={(e) => setSearchKeyword(e.target.value)}
              className="border-border bg-background text-foreground"
            />
            <div className="max-h-60 space-y-1 overflow-auto rounded-md border border-border p-1">
              {searchResults.length > 0 ? (
                searchResults.map((item) => (
                  <button
                    key={item.href}
                    type="button"
                    className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm text-foreground hover:bg-accent"
                    onClick={() => {
                      setSearchOpen(false)
                      setSearchKeyword("")
                      router.push(item.href)
                    }}
                  >
                    <span>{item.label}</span>
                    <span className="text-xs text-muted-foreground">{item.href}</span>
                  </button>
                ))
              ) : (
                <div className="px-2 py-3 text-sm text-muted-foreground">没有匹配结果</div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="border-border bg-popover text-popover-foreground sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>系统设置</DialogTitle>
            <DialogDescription>
              这里提供当前登录状态、接口地址和系统连通检查，先把管理台常用设置入口接实。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-border bg-background p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                  <ShieldCheck className="h-4 w-4 text-emerald-500" />
                  登录状态
                </div>
                <div className="text-sm text-muted-foreground">
                  {isLoggedIn ? "当前已登录检修域后台，可访问受控能力。" : "当前未登录，建议先进入登录页获取检修域令牌。"}
                </div>
              </div>
              <div className="rounded-lg border border-border bg-background p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                  <Server className="h-4 w-4 text-primary" />
                  API 地址
                </div>
                <div className="break-all text-sm text-muted-foreground">{getApiBase()}</div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-background p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
                <Wrench className="h-4 w-4 text-primary" />
                系统检查
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <button
                  type="button"
                  className="rounded-lg border border-border bg-card px-3 py-3 text-left transition-colors hover:bg-accent/50"
                  onClick={() => void runHealthCheck()}
                >
                  <div className="text-sm text-foreground">系统健康检查</div>
                  <div className="mt-1 text-xs text-muted-foreground">{healthStatus}</div>
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-border bg-card px-3 py-3 text-left transition-colors hover:bg-accent/50"
                  onClick={() => void runMaintenanceCheck()}
                >
                  <div className="text-sm text-foreground">检修域连通检查</div>
                  <div className="mt-1 text-xs text-muted-foreground">{maintenanceStatus}</div>
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-border bg-card px-3 py-3 text-left transition-colors hover:bg-accent/50"
                  onClick={() => void runReadinessCheck()}
                >
                  <div className="text-sm text-foreground">后端就绪检查</div>
                  <div className="mt-1 text-xs text-muted-foreground">{readinessStatus}</div>
                </button>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-background p-4">
              <div className="mb-3 text-sm font-medium text-foreground">账户操作</div>
              <div className="flex flex-wrap gap-2">
                {isLoggedIn ? (
                  <Button type="button" variant="outline" className="border-border" onClick={handleLogout}>
                    <LogOut className="mr-2 h-4 w-4" />
                    退出登录
                  </Button>
                ) : (
                  <Button type="button" variant="outline" className="border-border" onClick={handleOpenLogin}>
                    <LogIn className="mr-2 h-4 w-4" />
                    前往登录
                  </Button>
                )}
                <Button
                  type="button"
                  variant="outline"
                  className="border-border"
                  onClick={() => {
                    window.open(`${getApiBase()}/docs`, "_blank", "noopener,noreferrer")
                  }}
                >
                  查看接口文档
                </Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" className="border-border" onClick={() => setSettingsOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function NavItem({ children, active = false, href }: { children: React.ReactNode; active?: boolean; href: string }) {
  return (
    <Link
      href={href}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-accent text-foreground"
          : "text-muted-foreground hover:bg-accent/70 hover:text-foreground"
      }`}
    >
      {children}
    </Link>
  )
}

