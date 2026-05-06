"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Activity, ArrowRight, ClipboardCheck, Layers } from "lucide-react";
import Link from "next/link";

import { SectionBadge } from "@/shared/components/ui/section-badge";
import { ROUTES } from "@/shared/lib/routes";
import { ui } from "@/shared/theme/ui-tokens";
import { cn } from "@/shared/lib/utils";

type DemoStat = {
  label: string;
  value: string;
  sub: string;
  accent?: boolean;
};

type DemoFeature = {
  icon: ReactNode;
  title: string;
  description: string;
  status: string;
  panelTitle: string;
  workspaceKind: "retrieval" | "guidance" | "knowledge";
  stats: DemoStat[];
  aiTitle: string;
  aiDetail: string;
};

const features: DemoFeature[] = [
  {
    icon: <Activity className="h-5 w-5" />,
    title: "多模态知识检索",
    description: "支持文本、故障图片与设备型号输入，联动语义检索与跨模态匹配快速定位知识依据",
    status: "检索中",
    panelTitle: "知识检索视图 · 检修依据召回",
    workspaceKind: "retrieval",
    stats: [
      { label: "知识条目", value: "1,247", sub: "+12 今日" },
      { label: "命中片段", value: "23", sub: "-8 已过滤" },
      { label: "检索耗时", value: "156ms", sub: "P95", accent: true },
    ],
    aiTitle: "系统状态 · 智能检索中",
    aiDetail: "正在融合文本、图片与设备上下文，预计 6s 返回高相关知识依据",
  },
  {
    icon: <Layers className="h-5 w-5" />,
    title: "标准化作业指引",
    description: "将检索结果嵌入检修流程，生成步骤化操作指引、风险提示与合规提醒",
    status: "已生成",
    panelTitle: "作业指引视图 · 步骤预案生成",
    workspaceKind: "guidance",
    stats: [
      { label: "预案步骤", value: "38", sub: "-12 已完成" },
      { label: "待确认项", value: "17", sub: "+3 新增" },
      { label: "通过率", value: "98.2%", sub: "规则校验", accent: true },
    ],
    aiTitle: "系统状态 · 步骤预案生成中",
    aiDetail: "正在依据检修模板补全注意事项与风险提示，预计 18s 完成可执行指引",
  },
  {
    icon: <ClipboardCheck className="h-5 w-5" />,
    title: "知识沉淀与更新",
    description: "将检修结果、案例总结与修订意见回流知识库，形成审核发布与持续更新闭环",
    status: "已回流",
    panelTitle: "知识更新视图 · 案例审核发布",
    workspaceKind: "knowledge",
    stats: [
      { label: "知识条目", value: "12,406", sub: "+96 今日" },
      { label: "审核通过", value: "87%", sub: "+6% 周环比" },
      { label: "更新时间", value: "420ms", sub: "回写延迟", accent: true },
    ],
    aiTitle: "系统状态 · 知识闭环回流中",
    aiDetail: "正在整理案例结论与修订意见，预计 18s 完成回填建议并同步知识中心",
  },
];

const railItems = ["概览", "诊断中心", "设备管理", "工单管理", "知识中心", "系统设置"];

export function ProductDemo() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const activeFeature = features[activeIndex] ?? features[0];

  useEffect(() => {
    if (isPaused || features.length <= 1) return;
    const timer = window.setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % features.length);
    }, 5200);
    return () => window.clearInterval(timer);
  }, [isPaused]);

  return (
    <section id="overview" className={`scroll-mt-24 ${ui.section}`}>
      <div className={ui.container}>
        <div className={ui.sectionHeader}>
          <SectionBadge className="mb-4">产品演示</SectionBadge>
          <h2 className={`${ui.titleH2} mb-4`}>一个平台，全程可见</h2>
          <p className={`${ui.subtitle} mx-auto max-w-2xl`}>
            从多模态检索到步骤指引，再到知识回流与审核发布，每一步都在控制台实时呈现
          </p>
        </div>

        <div
          className="grid items-start gap-5 lg:grid-cols-[360px_1fr] lg:gap-9"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
        >
          <div className="space-y-3">
            {features.map((feature, i) => {
              const selected = activeIndex === i;
              return (
                <button
                  key={feature.title}
                  type="button"
                  onClick={() => {
                    setActiveIndex(i);
                    setIsPaused(false);
                  }}
                  aria-pressed={selected}
                  className={cn(
                    "group w-full min-h-[124px] rounded-[16px] border border-border bg-card p-4 text-left shadow-[0_8px_24px_rgba(15,23,42,0.04)] transition-all duration-250",
                    "hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-[0_12px_30px_rgba(0,0,0,0.24)]",
                    selected
                      ? "border-brand/55 bg-[linear-gradient(135deg,rgba(24,182,99,0.18),rgba(24,182,99,0.04)_62%)] shadow-[0_14px_34px_rgba(0,0,0,0.26)]"
                      : "hover:bg-[linear-gradient(135deg,rgba(24,182,99,0.08),rgba(24,182,99,0.02)_60%)]",
                  )}
                >
                  <div className="mb-3 flex items-center gap-3">
                    <div
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-bg-elevated text-text-tertiary transition-colors",
                        selected
                          ? "border-brand/45 bg-brand/16 text-brand-dark"
                          : "group-hover:border-brand/30 group-hover:bg-brand/12 group-hover:text-brand-dark",
                      )}
                    >
                      {feature.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-[15px] font-semibold text-text-primary">{feature.title}</h3>
                      <div className="mt-1 text-[11px] text-text-tertiary">
                        {feature.workspaceKind === "retrieval"
                          ? "检索工作台"
                          : feature.workspaceKind === "guidance"
                            ? "指引工作台"
                            : "知识工作台"}
                      </div>
                    </div>
                    <span
                      className={cn(
                        "rounded-full border border-border bg-bg-elevated px-2 py-0.5 text-[10px] font-medium text-text-tertiary transition-colors",
                        selected
                          ? "border-brand/35 bg-brand/12 text-brand-dark"
                          : "group-hover:border-brand/25 group-hover:bg-brand/10 group-hover:text-brand-dark",
                      )}
                    >
                      {feature.status}
                    </span>
                  </div>
                  <p className="text-[13px] leading-6 text-text-secondary">{feature.description}</p>
                </button>
              );
            })}

            <Link
              href={ROUTES.dashboard}
              className="mt-2 flex items-center gap-2 text-sm font-medium text-brand transition-colors hover:text-brand-light"
            >
              查看完整功能
              <ArrowRight className="h-4 w-4" />
            </Link>
            <div className="mt-3 flex items-center gap-1.5 pl-0.5">
              {features.map((feature, i) => (
                <button
                  key={feature.title}
                  type="button"
                  aria-label={`切换到${feature.title}`}
                  onClick={() => {
                    setActiveIndex(i);
                    setIsPaused(false);
                  }}
                  className={cn(
                    "h-1.5 rounded-full bg-border transition-all",
                    activeIndex === i ? "w-6 bg-brand" : "w-2.5 hover:bg-brand/60",
                  )}
                />
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="rounded-[20px] border border-border bg-card p-3 shadow-[0_18px_40px_rgba(15,23,42,0.08)]">
              <div className="relative overflow-hidden rounded-[16px] border border-[rgba(24,182,99,0.2)] bg-[#0b1018] p-3.5 shadow-[0_14px_32px_rgba(2,6,23,0.28)]">
                <div className="mb-3.5 flex items-center gap-2 border-b border-white/[0.06] pb-3">
                  <div className="flex gap-1.5">
                    <div className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]/90" />
                    <div className="h-2.5 w-2.5 rounded-full bg-[#ffbd2e]/90" />
                    <div className="h-2.5 w-2.5 rounded-full bg-[#28ca42]/90" />
                  </div>
                  <div className="flex-1 text-center text-[11px] text-[#c4ccda]">{activeFeature.panelTitle}</div>
                  <div className="flex items-center gap-1.5 rounded border border-brand/20 bg-brand/8 px-2 py-0.5">
                    <div className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-brand" />
                    <span className="text-[10px] font-medium text-brand">在线</span>
                  </div>
                </div>

                <div
                  key={activeFeature.workspaceKind}
                  className="grid grid-cols-1 gap-3 opacity-100 transition-all duration-300 lg:grid-cols-[120px_1fr]"
                >
                  <NavRail />
                  <div className="min-h-[372px] space-y-3">
                    <StatsRow stats={activeFeature.stats} />
                    {activeFeature.workspaceKind === "retrieval" ? <RetrievalWorkbench /> : null}
                    {activeFeature.workspaceKind === "guidance" ? <GuidanceWorkbench /> : null}
                    {activeFeature.workspaceKind === "knowledge" ? <KnowledgeWorkbench /> : null}
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md border border-white/[0.06] bg-white/[0.03]">
                      <span className="text-[10px] font-bold text-[#9ca8ba]">AI</span>
                    </div>
                    <div>
                      <div className="text-[11px] font-medium text-[#e7edf8]">{activeFeature.aiTitle}</div>
                      <div className="text-[10px] text-[#7f8ba1]">{activeFeature.aiDetail}</div>
                    </div>
                  </div>
                  <span className="rounded border border-brand/20 bg-brand/8 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-brand">
                    LIVE
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function NavRail() {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-[#0a1422] p-2">
      <div className="mb-2 text-[10px] text-[#8e9aaf]">FaultDiag</div>
      <div className="space-y-1">
        {railItems.map((item, idx) => (
          <div
            key={item}
            className={cn(
              "rounded-md px-2 py-1.5 text-[11px] transition-colors",
              idx === 1
                ? "border border-brand/20 bg-brand/10 text-[#e6fff2]"
                : "text-[#9ca8ba] hover:bg-white/[0.04] hover:text-[#d7deea]",
            )}
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function StatsRow({ stats }: { stats: DemoStat[] }) {
  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className={cn(
            "rounded-lg border p-3",
            stat.accent
              ? "border-[rgba(24,195,126,0.3)] bg-[rgba(24,195,126,0.08)]"
              : "border-white/[0.06] bg-white/[0.02]",
          )}
        >
          <div className="mb-1 text-[10px] text-[#9ca8ba]">{stat.label}</div>
          <div
            className={cn(
              "text-[34px] font-semibold tabular-nums leading-none tracking-tight",
              stat.accent ? "text-brand-light" : "text-[#e8edf7]",
            )}
          >
            {stat.value}
          </div>
          <div className={cn("mt-1 text-[10px] tabular-nums", stat.accent ? "text-brand/70" : "text-[#8a95a8]")}>{stat.sub}</div>
        </div>
      ))}
    </div>
  );
}

function RetrievalWorkbench() {
  const bars = [42, 71, 55, 79, 48, 84, 62, 76, 53];
  const alerts = [
    { name: "压缩机-A03", detail: "振动异常", time: "2分钟前", tone: "bg-landing-status-error" },
    { name: "电机-B12", detail: "温度过高", time: "5分钟前", tone: "bg-landing-status-warning" },
    { name: "泵组-C07", detail: "压力波动", time: "12分钟前", tone: "bg-brand" },
  ];

  return (
    <>
      <div className="grid gap-2.5 lg:grid-cols-[1.45fr_0.95fr] lg:items-stretch">
        <div className="h-[248px] rounded-lg border border-[rgba(24,195,126,0.22)] bg-[linear-gradient(180deg,rgba(24,195,126,0.08),rgba(255,255,255,0.02))] p-3 shadow-[0_0_0_1px_rgba(24,195,126,0.06)]">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] text-[#c8d0de]">检索趋势（近7日）</span>
            <span className="text-[10px] text-[#7f8ba1]">文本 / 图片 / 型号联合召回</span>
          </div>
          <div className="flex h-[158px] items-end justify-between gap-1 px-1">
            {bars.map((height, i) => (
              <div
                key={i}
                className={cn("landing-chart-bar w-[8px] shrink-0", i % 2 === 1 && "landing-chart-bar-highlight")}
                style={{ height: `${height}%` }}
              />
            ))}
          </div>
          <div className="mt-3 grid grid-cols-5 text-[10px] text-[#7f8ba1]">
            <span>文本</span>
            <span>图片</span>
            <span>型号</span>
            <span>召回</span>
            <span>定位</span>
          </div>
        </div>

        <div className="h-[248px] rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="text-[11px] font-medium text-[#c8d0de]">实时告警</span>
            <span className="text-[10px] text-[#7f8ba1]">最近 30 分钟检索状态</span>
          </div>
          <div className="space-y-1.5">
            {alerts.map((alert) => (
              <div key={alert.name} className="rounded border border-white/[0.04] bg-black/20 px-2.5 py-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className={cn("h-1.5 w-1.5 shrink-0 rounded-full", alert.tone)} />
                    <span className="truncate text-[11px] font-medium text-[#e7edf8]">{alert.name}</span>
                  </div>
                  <span className="text-[10px] text-[#7f8ba1]">{alert.time}</span>
                </div>
                <div className="mt-1 pl-3.5 text-[10px] text-[#8290a6]">{alert.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="h-[92px] rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
        <div className="mb-2 text-[11px] text-[#c8d0de]">检索链路吞吐（近7日）</div>
        <div className="grid grid-cols-5 gap-1.5 text-center">
          {[
            { label: "采集", value: "1247" },
            { label: "清洗", value: "312" },
            { label: "分析", value: "198" },
            { label: "定位", value: "156", accent: true },
            { label: "闭环", value: "142" },
          ].map((item) => (
            <div key={item.label} className="rounded-md border border-white/[0.04] bg-black/20 px-1.5 py-1.5">
              <div className={cn("text-[10px]", item.accent ? "text-brand" : "text-[#8a95a8]")}>{item.label}</div>
              <div className={cn("text-[11px] font-semibold", item.accent ? "text-brand-light" : "text-[#dbe3f2]")}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function GuidanceWorkbench() {
  const steps = [
    { id: "工步 01", title: "断电挂牌与现场确认", status: "合规校验已通过", accent: false },
    { id: "工步 02", title: "点火线束复核与绝缘测试", status: "需人工二次确认", accent: true },
    { id: "工步 03", title: "恢复供电与联调验证", status: "等待上一步完成", accent: false },
  ];
  const checks = [
    { title: "点火线束复核", meta: "高优先级", detail: "优先执行", tone: "text-brand" },
    { title: "断电挂牌确认", meta: "合规校验", detail: "需人工确认", tone: "text-[#f6c343]" },
    { title: "工步 07 扭矩参数", meta: "规则通过", detail: "参数已绑定", tone: "text-[#8a95a8]" },
  ];

  return (
    <>
      <div className="grid gap-2.5 lg:grid-cols-[1.3fr_0.9fr] lg:items-stretch">
        <div className="h-[248px] rounded-lg border border-[rgba(24,195,126,0.22)] bg-[linear-gradient(180deg,rgba(24,195,126,0.08),rgba(255,255,255,0.02))] p-3 shadow-[0_0_0_1px_rgba(24,195,126,0.06)]">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] text-[#c8d0de]">作业预案</span>
            <span className="text-[10px] text-[#7f8ba1]">按流程模板生成工步与注意事项</span>
          </div>
          <div className="space-y-2.5">
            {steps.map((step) => (
              <div
                key={step.id}
                className={cn(
                  "rounded-md border px-3 py-3",
                  step.accent ? "border-brand/25 bg-brand/10" : "border-white/[0.04] bg-black/20",
                )}
              >
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[10px] text-[#8a95a8]">{step.id}</span>
                  <span className={cn("text-[10px]", step.accent ? "text-brand" : "text-[#7f8ba1]")}>{step.status}</span>
                </div>
                <div className="text-[13px] font-medium text-[#e7edf8]">{step.title}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="h-[248px] rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="text-[11px] font-medium text-[#c8d0de]">风险 / 规则校验</span>
            <span className="text-[10px] text-[#7f8ba1]">最近 7 天执行状态</span>
          </div>
          <div className="space-y-1.5">
            {checks.map((check) => (
              <div key={check.title} className="rounded border border-white/[0.04] bg-black/20 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-medium text-[#e7edf8]">{check.title}</span>
                  <span className={cn("text-[10px]", check.tone)}>{check.meta}</span>
                </div>
                <div className="mt-1 text-[10px] text-[#8290a6]">{check.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="h-[92px] rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
        <div className="mb-2 text-[11px] text-[#c8d0de]">执行链路（近7日）</div>
        <div className="grid grid-cols-5 gap-1.5 text-center">
          {[
            { label: "生成", value: "96" },
            { label: "确认", value: "41" },
            { label: "执行", value: "28", accent: true },
            { label: "回填", value: "17" },
            { label: "归档", value: "14" },
          ].map((item) => (
            <div key={item.label} className="rounded-md border border-white/[0.04] bg-black/20 px-1.5 py-1.5">
              <div className={cn("text-[10px]", item.accent ? "text-brand" : "text-[#8a95a8]")}>{item.label}</div>
              <div className={cn("text-[11px] font-semibold", item.accent ? "text-brand-light" : "text-[#dbe3f2]")}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function KnowledgeWorkbench() {
  const reviewRows = [
    { title: "案例回填", note: "等待专家审核", value: "18" },
    { title: "知识修订", note: "已生成差异摘要", value: "06" },
    { title: "发布入库", note: "24h 内同步完成", value: "11", accent: true },
  ];
  const records = [
    { code: "CASE-018", detail: "油循环异常案例", status: "已审核发布" },
    { code: "SOP-042", detail: "步骤说明已修订", status: "等待同步" },
    { code: "MANUAL-07", detail: "来源片段已回写", status: "420ms" },
  ];

  return (
    <>
      <div className="grid gap-2.5 lg:grid-cols-[1.05fr_0.95fr] lg:items-stretch">
        <div className="h-[248px] rounded-lg border border-[rgba(24,195,126,0.22)] bg-[linear-gradient(180deg,rgba(24,195,126,0.08),rgba(255,255,255,0.02))] p-3 shadow-[0_0_0_1px_rgba(24,195,126,0.06)]">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] text-[#c8d0de]">审核发布链路</span>
            <span className="text-[10px] text-[#7f8ba1]">案例回填、专家审核与知识发布同步进行</span>
          </div>
          <div className="space-y-2.5">
            {reviewRows.map((row) => (
              <div key={row.title} className="rounded-md border border-white/[0.04] bg-black/20 px-3 py-3">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[11px] text-[#c8d0de]">{row.title}</span>
                  <span className={cn("text-[22px] font-semibold leading-none", row.accent ? "text-brand-light" : "text-[#e7edf8]")}>{row.value}</span>
                </div>
                <div className="text-[10px] text-[#7f8ba1]">{row.note}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="h-[248px] rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="text-[11px] font-medium text-[#c8d0de]">近期案例 / 回写记录</span>
            <span className="text-[10px] text-[#7f8ba1]">最近 24 小时更新结果</span>
          </div>
          <div className="space-y-1.5">
            {records.map((record, idx) => (
              <div key={record.code} className="rounded border border-white/[0.04] bg-black/20 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-medium text-[#e7edf8]">{record.code}</span>
                  <span className={cn("text-[10px]", idx === 0 || idx === 2 ? "text-brand" : "text-[#7f8ba1]")}>{record.status}</span>
                </div>
                <div className="mt-1 text-[10px] text-[#8290a6]">{record.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="h-[92px] rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
        <div className="mb-2 text-[11px] text-[#c8d0de]">闭环回流（近7日）</div>
        <div className="grid grid-cols-5 gap-1.5 text-center">
          {[
            { label: "回填", value: "63" },
            { label: "审核", value: "48" },
            { label: "修订", value: "22" },
            { label: "发布", value: "19", accent: true },
            { label: "复用", value: "11" },
          ].map((item) => (
            <div key={item.label} className="rounded-md border border-white/[0.04] bg-black/20 px-1.5 py-1.5">
              <div className={cn("text-[10px]", item.accent ? "text-brand" : "text-[#8a95a8]")}>{item.label}</div>
              <div className={cn("text-[11px] font-semibold", item.accent ? "text-brand-light" : "text-[#dbe3f2]")}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

