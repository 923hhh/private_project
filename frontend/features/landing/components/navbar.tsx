"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, Menu, X } from "lucide-react";
import { createPortal } from "react-dom";

import { cn } from "@/shared/lib/utils";

type NavLeaf = {
  label: string;
  href: string;
  description?: string;
};

type NavItem =
  | NavLeaf
  | {
      label: string;
      children: NavLeaf[];
    };

const navItems: NavItem[] = [
  { label: "主页", href: "#home" },
  { label: "平台概览", href: "#overview" },
  {
    label: "产品能力",
    children: [
      {
        label: "核心能力",
        href: "#capabilities",
        description: "全链路智能诊断能力",
      },
      {
        label: "诊断闭环",
        href: "#workflow",
        description: "5 步完成智能检修闭环",
      },
      {
        label: "业务价值",
        href: "#value",
        description: "围绕检测系统构建三项核心能力",
      },
    ],
  },
  { label: "应用场景", href: "#scenarios" },
  { label: "数据成效", href: "#metrics" },
];

const capabilitySectionIds = ["capabilities", "workflow", "value"];
const observedSectionIds = ["overview", ...capabilitySectionIds, "scenarios", "metrics"];

function isLeaf(item: NavItem): item is NavLeaf {
  return "href" in item;
}

export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<string>("home");
  const [mounted, setMounted] = useState(false);
  const [capabilityMenuOpen, setCapabilityMenuOpen] = useState(false);
  const closeTimerRef = useRef<number | null>(null);

  const clearCloseTimer = () => {
    if (closeTimerRef.current != null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const scrollToTopAndClearHash = () => {
    if (typeof window === "undefined") return;
    clearCloseTimer();
    setCapabilityMenuOpen(false);
    setMobileMenuOpen(false);
    setActiveSection("home");
    const cleanUrl = `${window.location.pathname}${window.location.search}`;
    window.history.replaceState({}, "", cleanUrl);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleAnchorClick = (href: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (href === "#home") {
      e.preventDefault();
      scrollToTopAndClearHash();
      return;
    }
    clearCloseTimer();
    setCapabilityMenuOpen(false);
    setMobileMenuOpen(false);
  };

  const topLevelActive = useMemo(() => {
    if (activeSection === "home") return "主页";
    if (activeSection === "overview") return "平台概览";
    if (capabilitySectionIds.includes(activeSection)) return "产品能力";
    if (activeSection === "scenarios") return "应用场景";
    if (activeSection === "metrics") return "数据成效";
    return "";
  }, [activeSection]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const getCurrentSection = () => {
      const viewportMid = window.innerHeight * 0.28;
      const candidates = observedSectionIds
        .map((id) => document.getElementById(id))
        .filter((el): el is HTMLElement => Boolean(el));

      let current = window.scrollY <= 24 ? "home" : observedSectionIds[0];
      for (const section of candidates) {
        const rect = section.getBoundingClientRect();
        if (rect.top <= viewportMid && rect.bottom >= viewportMid) {
          current = section.id;
          break;
        }
        if (rect.top <= viewportMid) current = section.id;
      }
      setActiveSection(current);
    };

    getCurrentSection();
    window.addEventListener("scroll", getCurrentSection, { passive: true });
    window.addEventListener("resize", getCurrentSection);
    return () => {
      window.removeEventListener("scroll", getCurrentSection);
      window.removeEventListener("resize", getCurrentSection);
    };
  }, []);

  if (!mounted) return null;

  return createPortal(
    <header className="fixed left-0 right-0 top-0 z-50 border-b border-border bg-white/72 backdrop-blur-[14px] dark:border-white/[0.06] dark:bg-[#071018]/60">
      <nav className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
        <div className="flex h-[72px] items-center justify-between">
          <button
            type="button"
            onClick={scrollToTopAndClearHash}
            className="group flex items-center gap-2 rounded-md transition-transform duration-200 ease-out hover:-translate-y-[1px] active:translate-y-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
            aria-label="返回顶部"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-brand/20 bg-brand/10 shadow-[0_0_0_0_rgba(34,197,94,0),0_0_0_0_rgba(34,197,94,0)] transition-all duration-200 ease-out group-hover:scale-[1.03] group-hover:border-brand/35 group-hover:bg-brand/15 group-hover:shadow-[0_0_0_4px_rgba(34,197,94,0.08),0_8px_20px_rgba(34,197,94,0.16)] group-active:scale-[0.98] dark:border-white/[0.08] dark:bg-white/[0.04] dark:group-hover:border-[#19e37d]/40 dark:group-hover:bg-[#19e37d]/12 dark:group-hover:shadow-[0_0_0_4px_rgba(25,227,125,0.10),0_8px_20px_rgba(25,227,125,0.18)]">
              <span className="text-sm font-bold text-brand-dark dark:text-[#19e37d]">FD</span>
            </div>
            <span className="text-[20px] font-semibold text-text-primary transition-colors duration-200 ease-out group-hover:text-[#0b1220] dark:text-[#f5f7fa] dark:group-hover:text-white">
              FaultDiag
            </span>
          </button>

          <div className="hidden md:flex md:items-center md:gap-6 lg:gap-7">
            {navItems.map((item) => {
              if (isLeaf(item)) {
                const active = topLevelActive === item.label;
                return (
                  <a
                    key={item.label}
                    href={item.href}
                    onClick={handleAnchorClick(item.href)}
                    className={cn(
                      "relative py-2 text-sm text-text-secondary transition-colors hover:text-text-primary dark:text-[#aab6c3] dark:hover:text-[#f5f7fa]",
                      active && "text-text-primary dark:text-[#f5f7fa]",
                    )}
                  >
                    {item.label}
                    <span
                      className={cn(
                        "absolute inset-x-0 -bottom-[13px] mx-auto h-0.5 w-5 rounded-full bg-brand transition-opacity",
                        active ? "opacity-100" : "opacity-0",
                      )}
                      aria-hidden
                    />
                  </a>
                );
              }

              const active = topLevelActive === item.label;
              return (
                <div
                  key={item.label}
                  className="relative"
                  onMouseEnter={() => {
                    clearCloseTimer();
                    setCapabilityMenuOpen(true);
                  }}
                  onMouseLeave={() => {
                    clearCloseTimer();
                    closeTimerRef.current = window.setTimeout(() => {
                      setCapabilityMenuOpen(false);
                      closeTimerRef.current = null;
                    }, 120);
                  }}
                >
                  <button
                    type="button"
                    className={cn(
                      "relative inline-flex items-center gap-1 py-2 text-sm text-text-secondary transition-colors hover:text-text-primary dark:text-[#aab6c3] dark:hover:text-[#f5f7fa]",
                      active && "text-text-primary dark:text-[#f5f7fa]",
                    )}
                    onClick={() => setCapabilityMenuOpen((prev) => !prev)}
                    aria-expanded={capabilityMenuOpen}
                    aria-haspopup="menu"
                  >
                    {item.label}
                    <ChevronDown className={cn("h-4 w-4 transition-transform", capabilityMenuOpen && "rotate-180")} />
                    <span
                      className={cn(
                        "absolute inset-x-0 -bottom-[13px] mx-auto h-0.5 w-5 rounded-full bg-brand transition-opacity",
                        active || capabilityMenuOpen ? "opacity-100" : "opacity-0",
                      )}
                      aria-hidden
                    />
                  </button>

                  <div
                    className={cn(
                      "absolute left-1/2 top-[calc(100%+14px)] w-[300px] -translate-x-1/2 rounded-2xl border border-border bg-white p-2 shadow-[0_18px_40px_rgba(15,23,42,0.10)] transition-[opacity,transform] duration-180 dark:border-white/[0.08] dark:bg-[#0f1720] dark:shadow-[0_18px_40px_rgba(0,0,0,0.35)]",
                      capabilityMenuOpen ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none -translate-y-1 opacity-0",
                    )}
                    role="menu"
                  >
                    {item.children.map((child) => (
                      <a
                        key={child.label}
                        href={child.href}
                        role="menuitem"
                        onClick={handleAnchorClick(child.href)}
                        className="block rounded-xl px-4 py-3 transition-colors hover:bg-brand/10 dark:hover:bg-brand/12"
                      >
                        <div className="text-sm font-medium text-text-primary dark:text-[#f5f7fa]">{child.label}</div>
                        <div className="mt-1 text-xs leading-5 text-text-secondary dark:text-[#8fa1b7]">
                          {child.description}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Link
              href="/login"
              className="py-2 text-sm text-text-secondary transition-colors hover:text-text-primary dark:text-[#aab6c3] dark:hover:text-[#f5f7fa]"
            >
              登录
            </Link>
            <Link
              href="/dashboard"
              className="rounded-md border border-[#0f172a] bg-[#111827] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0f172a] dark:border-white/[0.10] dark:bg-white/[0.06] dark:text-[#f5f7fa] dark:hover:bg-white/[0.10]"
            >
              进入演示
            </Link>
          </div>

          <button
            className="p-2 text-text-secondary hover:text-text-primary dark:text-[#aab6c3] dark:hover:text-[#f5f7fa] md:hidden"
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label="切换导航菜单"
          >
            {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

        {mobileMenuOpen && (
          <div className="border-t border-border py-4 dark:border-white/[0.06] md:hidden">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => {
                if (isLeaf(item)) {
                  const active = topLevelActive === item.label;
                  return (
                    <a
                      key={item.label}
                      href={item.href}
                      onClick={handleAnchorClick(item.href)}
                      className={cn(
                        "rounded-xl px-4 py-3 text-sm transition-colors",
                        active
                          ? "bg-brand/10 text-text-primary dark:bg-brand/14 dark:text-[#f5f7fa]"
                          : "text-text-secondary hover:bg-muted hover:text-text-primary dark:text-[#aab6c3] dark:hover:bg-white/[0.05] dark:hover:text-[#f5f7fa]",
                      )}
                    >
                      {item.label}
                    </a>
                  );
                }

                return (
                  <div key={item.label} className="rounded-xl border border-border/70 p-2 dark:border-white/[0.06]">
                    <div className="px-2 py-1.5 text-sm font-medium text-text-primary dark:text-[#f5f7fa]">
                      {item.label}
                    </div>
                    <div className="mt-1 space-y-1">
                      {item.children.map((child) => {
                        const active = activeSection === child.href.replace("#", "");
                        return (
                          <a
                            key={child.label}
                            href={child.href}
                            onClick={handleAnchorClick(child.href)}
                            className={cn(
                              "block rounded-lg px-3 py-2.5 transition-colors",
                              active
                                ? "bg-brand/10 text-text-primary dark:bg-brand/14 dark:text-[#f5f7fa]"
                                : "hover:bg-brand/10 dark:hover:bg-brand/12",
                            )}
                          >
                            <div className="text-sm text-text-primary dark:text-[#f5f7fa]">{child.label}</div>
                            <div className="mt-1 text-xs leading-5 text-text-secondary dark:text-[#8fa1b7]">
                              {child.description}
                            </div>
                          </a>
                        );
                      })}
                    </div>
                  </div>
                );
              })}

              <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4 dark:border-white/[0.06]">
                <Link
                  href="/login"
                  className="rounded-xl px-4 py-3 text-left text-sm text-text-secondary transition-colors hover:bg-muted hover:text-text-primary dark:text-[#aab6c3] dark:hover:bg-white/[0.05] dark:hover:text-[#f5f7fa]"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  登录
                </Link>
                <Link
                  href="/dashboard"
                  className="mx-1 rounded-xl border border-[#0f172a] bg-[#111827] py-3 text-center text-sm font-medium text-white transition-colors hover:bg-[#0f172a] dark:border-white/[0.10] dark:bg-white/[0.06] dark:text-[#f5f7fa] dark:hover:bg-white/[0.10]"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  进入演示
                </Link>
              </div>
            </div>
          </div>
        )}
      </nav>
    </header>,
    document.body,
  );
}

