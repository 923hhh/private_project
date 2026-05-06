"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Play } from "lucide-react";
import Link from "next/link";
import { fetchWorkbenchOverview, fetchHealth } from "@/features/dashboard/api";
import { ROUTES } from "@/shared/lib/routes";
import { cn } from "@/shared/lib/utils";

import { Button } from "@/shared/components/ui/button";
import { SectionBadge } from "@/shared/components/ui/section-badge";
import { ui } from "@/shared/theme/ui-tokens";

function formatInt(n: number) {
  return n.toLocaleString("en-US");
}

function randDelta(maxAbs: number) {
  // 随机小幅变化，避免 0
  const v = Math.floor(Math.random() * (maxAbs * 2 + 1)) - maxAbs;
  return v === 0 ? 1 : v;
}

type TrendBar = { id: string; h: number };

function randBarHeight() {
  // 高度随机但克制：避免过矮/过满
  return Math.max(26, Math.min(92, 40 + Math.floor(Math.random() * 46)));
}

type Severity = "high" | "medium" | "low";
type AlertItem = {
  id: string;
  device: string;
  type: string;
  severity: Severity;
  createdAtMs: number;
  entering?: boolean;
  exiting?: boolean;
};

function useTweenNumber(target: number, durationMs = 700) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);
  const fromRef = useRef(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    fromRef.current = value;
    startRef.current = null;

    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    const tick = (t: number) => {
      if (startRef.current === null) startRef.current = t;
      const p = Math.min(1, (t - startRef.current) / durationMs);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - p, 3);
      const next = Math.round(fromRef.current + (target - fromRef.current) * eased);
      setValue(next);
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, durationMs]);

  return value;
}

export function Hero() {
  const trendGlowThreshold = 72; // 高于该阈值发光
  const barCount = 12;
  const barWidthPx = 5;
  // 注意：首屏必须是确定性的（避免 SSR/CSR hydration mismatch）
  const [trendBars, setTrendBars] = useState<TrendBar[]>(() => {
    const initialHeights = [41, 68, 52, 74, 46, 82, 58, 71, 49, 77, 63, 55];
    return initialHeights.slice(0, barCount).map((h, i) => ({ id: `bar-${i}`, h }));
  });
  const [shifting, setShifting] = useState(false);
  const shiftTimeoutRef = useRef<number | null>(null);
  const nextBarIdRef = useRef(barCount);
  const trendRowRef = useRef<HTMLDivElement | null>(null);
  const [trendStepPx, setTrendStepPx] = useState<number>(barWidthPx + 4);

  const [kpi, setKpi] = useState(() => ({
    devices: { value: 1247, delta: 12 },
    alerts: { value: 23, delta: -8 },
    done: { value: 156, delta: 34 },
  }));
  const kpiIntervalRef = useRef<number | null>(null);
  const trendIntervalRef = useRef<number | null>(null);
  const alertsIntervalRef = useRef<number | null>(null);
  const alertExitTimersRef = useRef<number[]>([]);
  const alertEnterTimersRef = useRef<number[]>([]);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const [alerts, setAlerts] = useState<AlertItem[]>(() => [
    { id: "a0", device: "压缩机-A03", type: "振动异常", severity: "high", createdAtMs: Date.now() - 2 * 60_000 },
    { id: "a1", device: "电机-B12", type: "温度过高", severity: "medium", createdAtMs: Date.now() - 5 * 60_000 },
    { id: "a2", device: "泵组-C07", type: "压力波动", severity: "low", createdAtMs: Date.now() - 12 * 60_000 },
  ]);
  const alertSeqRef = useRef(3);

  const formatRelative = (createdAtMs: number) => {
    const diff = Math.max(0, nowMs - createdAtMs);
    if (diff < 30_000) return "刚刚";
    const mins = Math.max(1, Math.round(diff / 60_000));
    return `${mins}分钟前`;
  };

  const randomAlert = (): Omit<AlertItem, "id" | "createdAtMs"> => {
    const devices = ["压缩机-A03", "电机-B12", "泵组-C07", "风机-D08", "阀门-E02", "轴承-F11"];
    const types = ["振动异常", "温度过高", "压力波动", "电流偏移", "润滑不足", "噪声升高"];
    const severity: Severity = (() => {
      const r = Math.random();
      return r < 0.25 ? "high" : r < 0.65 ? "medium" : "low";
    })();
    const device = devices[Math.floor(Math.random() * devices.length)] ?? devices[0]!;
    const type = types[Math.floor(Math.random() * types.length)] ?? types[0]!;
    return { device, type, severity };
  };

  // 首次进入：从 0 滚动到初始值；之后每 2s 小幅随机变动并同步滚动
  useEffect(() => {
    const tick = () => {
      setKpi((prev) => {
        const nextDevicesDelta = randDelta(20);
        const nextAlertsDelta = randDelta(6);
        const nextDoneDelta = randDelta(12);

        return {
          devices: {
            value: Math.max(0, prev.devices.value + nextDevicesDelta),
            delta: nextDevicesDelta,
          },
          alerts: {
            value: Math.max(0, prev.alerts.value + nextAlertsDelta),
            delta: nextAlertsDelta,
          },
          done: {
            value: Math.max(0, prev.done.value + nextDoneDelta),
            delta: nextDoneDelta,
          },
        };
      });
    };

    // 2s 后开始循环变动
    const timeoutId = window.setTimeout(() => {
      tick();
      kpiIntervalRef.current = window.setInterval(tick, 2000);
    }, 2000);

    return () => {
      window.clearTimeout(timeoutId);
      if (kpiIntervalRef.current) window.clearInterval(kpiIntervalRef.current);
    };
  }, []);

  // 诊断趋势：每 2s 向左滚动一格，右侧生成新柱子（高度随机）
  useEffect(() => {
    const calcStep = () => {
      const el = trendRowRef.current;
      if (!el) return;
      const w = el.getBoundingClientRect().width;
      // justify-between 时，相邻柱子起点距离 = (容器宽度 - 柱子宽度) / (n-1)
      const step = barCount > 1 ? (w - barWidthPx) / (barCount - 1) : w;
      if (Number.isFinite(step) && step > 0) setTrendStepPx(step);
    };

    calcStep();
    window.addEventListener("resize", calcStep);

    const tick = () => {
      setShifting(true);
      if (shiftTimeoutRef.current) window.clearTimeout(shiftTimeoutRef.current);
      shiftTimeoutRef.current = window.setTimeout(() => {
        setTrendBars((prev) => {
          const next = prev.slice(1);
          next.push({ id: `bar-${nextBarIdRef.current++}`, h: randBarHeight() });
          return next;
        });
        setShifting(false);
      }, 620);
    };

    trendIntervalRef.current = window.setInterval(tick, 2000);
    return () => {
      if (trendIntervalRef.current) window.clearInterval(trendIntervalRef.current);
      if (shiftTimeoutRef.current) window.clearTimeout(shiftTimeoutRef.current);
      window.removeEventListener("resize", calcStep);
    };
  }, []);

  // 实时告警：每 2s 顶部弹出新告警；底部淡出后移除；联动“今日告警”
  useEffect(() => {
    const maxAlerts = 3;
    const exitMs = 520;

    // 时间持续更新（列表时间不会“卡住”）
    const nowTimer = window.setInterval(() => setNowMs(Date.now()), 1000);

    const tick = () => {
      setAlerts((prev) => {
        const next: AlertItem[] = [
          {
            id: `a${alertSeqRef.current++}`,
            createdAtMs: Date.now(),
            entering: true,
            ...randomAlert(),
          },
          ...prev,
        ];

        // 让最新告警从淡入开始（下一帧移除 entering）
        const enterId = next[0]!.id;
        const enterTimer = window.setTimeout(() => {
          setAlerts((curr) => curr.map((x) => (x.id === enterId ? { ...x, entering: false } : x)));
        }, 20);
        alertEnterTimersRef.current.push(enterTimer);

        if (next.length > maxAlerts) {
          const idx = maxAlerts;
          if (next[idx]) next[idx] = { ...next[idx]!, exiting: true };
          const timer = window.setTimeout(() => {
            setAlerts((curr) => curr.filter((x) => x.id !== next[idx]!.id));
          }, exitMs);
          alertExitTimersRef.current.push(timer);
          return next.slice(0, maxAlerts + 1);
        }
        return next;
      });
    };

    alertsIntervalRef.current = window.setInterval(tick, 2000);
    return () => {
      if (alertsIntervalRef.current) window.clearInterval(alertsIntervalRef.current);
      window.clearInterval(nowTimer);
      alertExitTimersRef.current.forEach((t) => window.clearTimeout(t));
      alertExitTimersRef.current = [];
      alertEnterTimersRef.current.forEach((t) => window.clearTimeout(t));
      alertEnterTimersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const devicesDisplay = useTweenNumber(kpi.devices.value, 820);
  const alertsDisplay = useTweenNumber(kpi.alerts.value, 740);
  const doneDisplay = useTweenNumber(kpi.done.value, 780);

  const stats = useMemo(
    () => [
      { label: "在线设备", value: devicesDisplay, delta: kpi.devices.delta, isMain: false },
      { label: "今日告警", value: alertsDisplay, delta: kpi.alerts.delta, isMain: false },
      { label: "诊断完成", value: doneDisplay, delta: kpi.done.delta, isMain: true },
    ],
    [alertsDisplay, devicesDisplay, doneDisplay, kpi.alerts.delta, kpi.devices.delta, kpi.done.delta],
  );

  return (
    <section id="home" className="relative overflow-hidden pt-24 pb-12 lg:pt-28 lg:pb-14">
      {/* 背景光晕层 */}
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div
          className="absolute -left-24 -top-24 h-[460px] w-[560px] rounded-full blur-[90px]"
          style={{ background: "radial-gradient(ellipse, rgba(148,163,184,0.2) 0%, transparent 70%)" }}
        />
        <div
          className="absolute -right-12 top-1/4 h-[420px] w-[520px] rounded-full blur-[110px]"
          style={{ background: "radial-gradient(ellipse, rgba(24,182,99,0.12) 0%, transparent 72%)" }}
        />
      </div>
      <div className={`${ui.container} relative`}>
        <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
          {/* Left content */}
          <div className="text-center lg:text-left">
            <SectionBadge className="mb-5 text-[13px]">多模态智能检修系统</SectionBadge>

            {/* 层级：说明(微) → 主标题(最大) → 强调行(中) → 收束行(小) */}
            <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.2em] text-text-tertiary sm:text-xs">
              面向检修闭环的智能辅助平台
            </p>
            <h1 className="mb-3 text-4xl font-bold leading-[1.06] tracking-[-0.045em] text-text-primary sm:text-5xl lg:text-[64px]">
              <span className="block">让故障定位</span>
              <span className="block">从数小时缩短到</span>
              <span className="block">
                <span className="hero-accent">几分钟</span>
              </span>
            </h1>
            <p className="mx-auto mb-8 max-w-[500px] text-[16px] leading-7 text-text-secondary lg:mx-0">
              融合文本、图片、设备型号等多模态输入，结合检索增强与作业闭环，快速完成知识定位、步骤指引与结果回填。
            </p>

            <div className="mt-6 flex h-12 flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center lg:justify-start">
              <Button
                variant="brand"
                size="marketingLg"
                className="h-12 rounded-xl bg-brand text-[#04120b] shadow-[0_12px_32px_rgba(24,195,126,0.24)] hover:bg-brand-dark hover:shadow-[0_16px_34px_rgba(24,195,126,0.28)]"
                asChild
              >
                <Link
                  href={ROUTES.dashboard}
                  onClick={() => {
                    void fetchWorkbenchOverview();
                  }}
                >
                  立即体验
                  <ArrowRight className="h-4 w-4 opacity-90" />
                </Link>
              </Button>
              <Button
                type="button"
                variant="brandSecondary"
                size="marketingLg"
                className="h-12 rounded-xl border-[#dde5ec] bg-card text-[#111827] hover:bg-bg-elevated dark:border-white/[0.10] dark:bg-white/[0.04] dark:text-[#e7edf3] dark:hover:bg-white/[0.08] dark:hover:text-[#f5f7fa]"
                onClick={() => {
                  void fetchHealth();
                }}
              >
                <Play className="h-4 w-4 opacity-80" />
                查看能力
              </Button>
            </div>

            {/* Trust indicators */}
            <div className="mt-10 border-t border-border/80 pt-5">
              <p className="mb-5 text-[13px] leading-snug text-landing-text-muted">
                面向 B/S 架构交付，支持可交互 Web 界面、多模态大模型 API 接入与龙架构服务器部署要求。
              </p>
              <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 lg:justify-start">
                {["多模态知识检索", "标准化作业指引", "知识沉淀与更新", "工单闭环追踪"].map((name, i) => (
                  <span key={name} className="inline-flex items-center gap-x-3">
                    {i > 0 ? (
                      <span className="hidden select-none text-[10px] text-[rgba(255,255,255,0.2)] sm:inline" aria-hidden>
                        ·
                      </span>
                    ) : null}
                    <span className="cursor-default text-[11px] font-medium tracking-[0.08em] text-landing-text-faint transition-opacity duration-200 hover:text-landing-text-subtle sm:text-xs">
                      {name}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Right content - Product preview */}
          <div className="relative">
            <div className="mx-auto max-w-[560px] rounded-[20px] border border-white/[0.08] bg-card p-3 shadow-[0_20px_50px_rgba(0,0,0,0.28)] sm:p-3.5">
              <div className="relative rounded-[16px] border border-[rgba(24,195,126,0.18)] bg-[#0c1320] p-3.5 shadow-[0_12px_30px_rgba(2,6,23,0.24)] sm:p-4">
                <div className="animate-float-glow absolute right-3 top-3 rounded-md border border-white/[0.08] bg-[#f4f7f5] px-2.5 py-2 sm:right-4 sm:top-4">
                  <div className="flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-accent-soft">
                      <div className="h-2 w-2 rounded-full bg-accent" />
                    </div>
                    <div>
                      <div className="text-[11px] font-medium text-[#0f172a]">诊断完成</div>
                      <div className="text-[10px] text-[#6b7280]">电机-B12 已恢复</div>
                    </div>
                  </div>
                </div>
                {/* Window header */}
                <div className="mb-3.5 flex items-center gap-2 border-b border-white/[0.08] pb-3.5 pr-24 sm:pr-28">
                  <div className="flex gap-1.5">
                    <div className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]/90" />
                    <div className="h-2.5 w-2.5 rounded-full bg-[#ffbd2e]/90" />
                    <div className="h-2.5 w-2.5 rounded-full bg-[#28ca42]/90" />
                  </div>
                  <div className="flex-1 text-center">
                    <span className="text-[11px] text-[#d5deec]">故障诊断控制台</span>
                  </div>
                </div>

                {/* Mock dashboard content */}
                <div className="space-y-3">
                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-2.5">
                    {stats.map((stat) => {
                      const isMain = stat.isMain;
                      return (
                        <div
                          key={stat.label}
                          className={`rounded-md border p-2.5 sm:p-3 ${isMain
                              ? "border-[rgba(24,195,126,0.28)] bg-[linear-gradient(135deg,rgba(6,45,34,0.96),rgba(4,33,26,0.96)_65%)]"
                              : "border-white/[0.06] bg-white/[0.03]"
                            }`}
                        >
                          <div className={isMain ? "mb-1 text-[11px] text-brand/70" : "mb-1 text-[11px] text-[#8fa1b7]"}>{stat.label}</div>
                          <div
                            className={
                              isMain
                                ? "text-[32px] font-semibold leading-none tracking-tight text-brand-light sm:text-[34px]"
                                : "text-[34px] font-semibold tabular-nums leading-none tracking-tight text-[#e7edf8]"
                            }
                          >
                            {formatInt(stat.value)}
                          </div>
                          <div
                            className={`text-[11px] tabular-nums ${isMain ? "font-medium text-[rgba(74,222,128,0.7)]" : "text-[#7f8ba1]"
                              }`}
                          >
                            {stat.delta >= 0 ? `+${stat.delta}` : `${stat.delta}`}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Alert list preview */}
                  <div className="rounded-md border border-white/[0.06] bg-white/[0.03] p-2.5 sm:p-3">
                    <div className="mb-2.5 text-[11px] text-[#c8d0de]">实时告警</div>
                    <div className="space-y-2">
                      {alerts.slice(0, 3).map((alert) => (
                        <div
                          key={alert.id}
                          className={cn(
                            "flex items-center justify-between rounded border border-white/[0.04] bg-black/20 px-2 py-1.5",
                            "transition-[opacity,transform] duration-500 ease-out",
                            // 淡入：不做位移弹入
                            alert.entering ? "opacity-0" : "opacity-100",
                            // 底部淡出：仅淡出，不做位移
                            alert.exiting ? "opacity-0" : "",
                          )}
                        >
                          <div className="flex min-w-0 items-center gap-2">
                            <div
                              className={`h-1.5 w-1.5 shrink-0 rounded-full ${alert.severity === "high"
                                  ? "bg-landing-status-error"
                                  : alert.severity === "medium"
                                    ? "bg-landing-status-warning"
                                    : "bg-landing-status-info"
                                }`}
                            />
                            <span className="truncate text-[11px] text-[#e7edf8]">{alert.device}</span>
                            <span className="hidden truncate text-[11px] text-[#8290a6] sm:inline">
                              {alert.type}
                            </span>
                          </div>
                          <span className="shrink-0 pl-2 text-[10px] tabular-nums text-[#7f8ba1]">
                            {formatRelative(alert.createdAtMs)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Chart placeholder */}
                  <div className="rounded-md border border-white/[0.06] bg-white/[0.03] p-2.5 sm:p-3">
                    <div className="mb-2 text-[11px] text-[#c8d0de]">诊断趋势</div>
                    <div className="overflow-hidden">
                      <div
                        ref={trendRowRef}
                        className="flex h-[72px] w-full items-end justify-between px-0.5"
                        style={{
                          transform: shifting ? `translateX(-${trendStepPx}px)` : "translateX(0px)",
                          transition: shifting ? "transform 620ms ease" : "none",
                          willChange: "transform",
                        }}
                      >
                        {trendBars.map((b) => {
                          const isHot = b.h >= trendGlowThreshold;
                          return (
                            <div
                              key={b.id}
                              className={`landing-chart-bar w-[5px] shrink-0 ${isHot ? "landing-chart-bar-highlight" : ""}`}
                              style={{ height: `${b.h}%` } as CSSProperties}
                            />
                          );
                        })}
                      </div>
                    </div>
                    <div className="mt-2 flex justify-between text-[11px] tracking-[-0.01em] text-[#7f8ba1]">
                      <span>近 12 周</span>
                      <span>单位：次 / 周</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-2.5 rounded-md border border-white/[0.08] bg-[#111827] px-2.5 py-2 sm:px-3 sm:py-2.5">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-white/[0.06] bg-[#0f172a]">
                        <span className="text-[10px] font-semibold text-[#94a3b8]">AI</span>
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-[11px] font-medium text-[#d1d5db]">系统状态 · 智能分析中</div>
                        <div className="truncate text-[10px] text-[#9ca3af]">正在生成诊断报告 · 预计 18s</div>
                      </div>
                    </div>
                    <span className="shrink-0 rounded border border-[rgba(74,222,128,0.2)] bg-[rgba(74,222,128,0.08)] px-1.5 py-0.5 text-[8px] font-medium tabular-nums tracking-wide text-[rgba(74,222,128,0.95)]">
                      LIVE
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

