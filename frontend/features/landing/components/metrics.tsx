"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Database, Info } from "lucide-react";
import { SectionDividerCue } from "@/features/landing/components/section-divider-cue";
import { SectionBadge } from "@/shared/components/ui/section-badge";
import { cn } from "@/shared/lib/utils";
import { ui } from "@/shared/theme/ui-tokens";

const metrics = [
  {
    key: "time",
    target: 3,
    from: 9,
    prefix: "< ",
    suffix: "min",
    label: "检索响应时长",
    description: "从输入问题到返回知识依据",
    caliber: "口径：从提交文本 / 图片 / 型号问题到返回首屏检索结果的平均耗时，基于演示样本统计。",
    featured: false as const,
  },
  {
    key: "hit",
    target: 94.7,
    from: 72,
    suffix: "%",
    label: "步骤生成成功率",
    description: "可生成有效步骤预案",
    caliber: "口径：检索命中后成功生成结构化步骤预案的任务占比，来自演示任务集回放。",
    featured: false as const,
  },
  {
    key: "close",
    target: 98.2,
    from: 81,
    suffix: "%",
    label: "工单闭环率",
    description: "检修流程从创建到结单",
    caliber: "口径：工单从知识检索、步骤执行、结果回填到审核结单的完整闭环完成率。",
    featured: true as const,
  },
  {
    key: "reuse",
    target: 85,
    from: 58,
    suffix: "%+",
    label: "知识复用率",
    description: "历史案例与手册被再次命中",
    caliber: "口径：历史案例、手册片段与已发布知识条目在后续检修任务中被有效调用的比例。",
    featured: false as const,
  },
];
export function Metrics() {
  const sectionRef = useRef<HTMLElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [entered, setEntered] = useState(false);
  const [focusIndex, setFocusIndex] = useState<number | null>(null);
  const [values, setValues] = useState(() => metrics.map((m) => m.from));
  const [glowLeft, setGlowLeft] = useState(0);
  const [glowTop, setGlowTop] = useState(0);
  const [glowWidth, setGlowWidth] = useState(180);
  const [glowHeight, setGlowHeight] = useState(120);
  const playedRef = useRef(false);

  useEffect(() => {
    const node = sectionRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting || playedRef.current) return;
        playedRef.current = true;
        setEntered(true);
      },
      { threshold: 0.32 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!entered) return;
    const timers: number[] = [];
    const rafIds: number[] = [];

    metrics.forEach((metric, index) => {
      const duration = 1000 + index * 120;
      const delay = index * 100;
      const timer = window.setTimeout(() => {
        const start = performance.now();
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / duration);
          const eased = 1 - Math.pow(1 - t, 3);
          const current = metric.from + (metric.target - metric.from) * eased;
          setValues((prev) => {
            const next = [...prev];
            next[index] = current;
            return next;
          });
          if (t < 1) {
            const id = window.requestAnimationFrame(tick);
            rafIds.push(id);
          }
        };
        const id = window.requestAnimationFrame(tick);
        rafIds.push(id);
      }, delay);
      timers.push(timer);
    });

    return () => {
      timers.forEach((t) => window.clearTimeout(t));
      rafIds.forEach((id) => window.cancelAnimationFrame(id));
    };
  }, [entered]);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;

    const updateGlow = () => {
      const focused = panel.querySelector<HTMLElement>(`[data-metric-index="${focusIndex}"]`);
      if (!focused) return;
      const panelRect = panel.getBoundingClientRect();
      const cardRect = focused.getBoundingClientRect();
      const centerX = cardRect.left + cardRect.width / 2 - panelRect.left;
      const centerY = cardRect.top + cardRect.height / 2 - panelRect.top;
      const targetWidth = Math.max(140, Math.min(220, cardRect.width * 0.58));
      const targetHeight = Math.max(96, Math.min(170, cardRect.height * 0.56));
      setGlowWidth(targetWidth);
      setGlowHeight(targetHeight);
      setGlowLeft(centerX - targetWidth / 2);
      setGlowTop(centerY - targetHeight / 2);
    };

    updateGlow();
    const ro = new ResizeObserver(updateGlow);
    ro.observe(panel);
    const focused = panel.querySelector<HTMLElement>(`[data-metric-index="${focusIndex}"]`);
    if (focused) ro.observe(focused);
    window.addEventListener("resize", updateGlow);

    return () => {
      ro.disconnect();
      window.removeEventListener("resize", updateGlow);
    };
  }, [focusIndex, entered]);

  const displayed = useMemo(
    () =>
      metrics.map((metric, index) => {
        const v = values[index] ?? metric.target;
        const formatted =
          metric.suffix?.includes("%") || metric.suffix === "min"
            ? v.toFixed(metric.target % 1 === 0 ? 0 : 1)
            : Math.round(v).toString();
        return `${metric.prefix ?? ""}${formatted}${metric.suffix ?? ""}`;
      }),
    [values],
  );

  return (
    <section id="metrics" ref={sectionRef} className={`scroll-mt-24 ${ui.section}`}>
      <div className={ui.container}>
        <SectionDividerCue
          badge={<SectionBadge className="mb-4">能力验证</SectionBadge>}
          title={<h2 className={`${ui.titleH2} mb-4`}>用数据验证系统能力</h2>}
          description={<p className={`${ui.subtitle} mx-auto max-w-2xl`}>围绕检索、步骤预案、闭环和知识复用四条链路展示演示验证结果</p>}
        />

        <div ref={panelRef} className={`${ui.panel} relative min-h-[176px] overflow-hidden`}>
          {/* 顶部渐变线 */}
          <div
            className="h-px w-full"
            style={{ background: "linear-gradient(90deg, transparent 0%, rgba(24,182,99,0.24) 30%, rgba(24,182,99,0.45) 50%, rgba(24,182,99,0.24) 70%, transparent 100%)" }}
            aria-hidden
          />
          <div
            className="pointer-events-none absolute rounded-full bg-[radial-gradient(circle,rgba(24,182,99,0.14),transparent_70%)] transition-[left,top,width,height,opacity] duration-300"
            style={{
              left: `${glowLeft}px`,
              top: `${glowTop}px`,
              width: `${glowWidth}px`,
              height: `${glowHeight}px`,
              opacity: entered && focusIndex != null ? 1 : 0,
            }}
            aria-hidden
          />
          <div
            className="grid sm:grid-cols-2 lg:grid-cols-4"
            onMouseLeave={() => setFocusIndex(null)}
          >
            {metrics.map((metric, index) => (
              <button
                key={metric.key}
                type="button"
                data-metric-index={index}
                onMouseEnter={() => setFocusIndex(index)}
                onClick={() => setFocusIndex(index)}
                className={cn(
                  "relative z-10 flex min-h-[160px] flex-col items-center justify-center px-6 py-8 text-center transition-all duration-300 sm:min-h-[180px] lg:px-8 lg:py-10",
                  entered ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
                  focusIndex === index ? "scale-[1.01]" : "scale-100",
                  index < metrics.length - 1 ? "border-b border-border/20 sm:border-b-0 lg:border-r lg:border-border/25" : "",
                )}
                style={{ transitionDelay: `${index * 90}ms` }}
              >
                <div
                  className={cn(
                    "text-4xl font-semibold tracking-[-0.05em] sm:text-[46px] lg:text-[52px]",
                    focusIndex === index ? "gradient-number" : "text-text-primary",
                  )}
                >
                  {displayed[index]}
                </div>
                <div className="mt-3 text-base font-medium text-text-primary sm:text-lg">{metric.label}</div>
                <div className="mt-2 max-w-[220px] text-sm leading-6 text-text-secondary">{metric.description}</div>
              </button>
            ))}
          </div>
        </div>

        <div
          className={cn(
            "mt-4 flex items-start gap-2 rounded-xl border border-border/70 bg-panel/70 px-4 py-3 text-[13px] leading-6 text-text-secondary shadow-[0_4px_14px_rgba(15,23,42,0.06)] transition-all duration-300",
            entered ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
          )}
        >
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
          <div>
            {focusIndex != null ? (
              <>
                <span className="font-semibold text-text-primary">{metrics[focusIndex]?.label}</span>
                <span className="ml-2">{metrics[focusIndex]?.caliber}</span>
              </>
            ) : (
              <span>滑入上方指标卡后查看对应口径说明。</span>
            )}
          </div>
        </div>

        <div className={cn("mt-8 flex items-center justify-center gap-2 text-center transition-opacity duration-300", entered ? "opacity-100" : "opacity-0")}>
          <Database className="h-4 w-4 text-text-secondary" />
          <p className="text-sm text-text-secondary">
            数据来源：演示任务集、样本案例回放与检修闭环流程验证
          </p>
        </div>
      </div>
    </section>
  );
}

