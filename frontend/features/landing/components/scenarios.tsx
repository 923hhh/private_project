"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import useEmblaCarousel from "embla-carousel-react";
import {
  Flame,
  Layers,
  Cog,
  Zap,
  Train,
  FlaskConical,
  CircleCheck,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ArrowUpRight,
} from "lucide-react";
import { SectionDividerCue } from "@/features/landing/components/section-divider-cue";
import { Reveal } from "@/shared/components/ui/reveal";
import { SectionBadge } from "@/shared/components/ui/section-badge";
import { ui } from "@/shared/theme/ui-tokens";
import { cn } from "@/shared/lib/utils";

type Scenario = {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  industry: string;
  title: string;
  description: string;
  tag: string;
  cluster: "流程工业" | "离散制造";
  subtitle: string;
  devices: string[];
  diagnoses: string[];
  dataTypes: string[];
  benefits: string[];
  caseHint: string;
};

const scenarios: Scenario[] = [
  {
    id: "petro",
    icon: Flame,
    industry: "石油化工",
    title: "炼化装置预测性维护",
    description: "实时监测压缩机、泵组等关键设备，提前预警腐蚀与泄漏风险",
    tag: "高频",
    cluster: "流程工业",
    subtitle: "针对压缩机、泵组、换热器等关键设备的异常预警与健康管理。",
    devices: ["往复式压缩机", "离心泵", "换热器", "塔器及管道"],
    diagnoses: ["异常振动", "密封泄漏", "结垢堵塞", "腐蚀减薄"],
    dataTypes: ["振动信号", "温度数据", "压力数据", "电流/功率数据"],
    benefits: ["非计划停机下降 30%+", "巡检效率提升", "维修成本下降", "设备寿命延长"],
    caseHint: "某炼化园区压缩机故障预警项目，3个月内将突发停机率降低 32%。",
  },
  {
    id: "steel",
    icon: Layers,
    industry: "钢铁冶金",
    title: "高炉与轧机健康管理",
    description: "融合温度、振动、电流多维传感器，精准定位轧辊磨损与炉况异常",
    tag: "推荐",
    cluster: "流程工业",
    subtitle: "围绕高炉、连铸、轧机核心环节，实现设备健康评分与异常根因定位。",
    devices: ["高炉鼓风机", "连铸机", "轧机主传动", "轧辊系统"],
    diagnoses: ["轧辊磨损", "炉况波动", "电机异常发热", "传动冲击"],
    dataTypes: ["电流电压", "振动频谱", "温度曲线", "转速扭矩"],
    benefits: ["成材率提升", "停机损失降低", "设备寿命延长", "检修节奏可控"],
    caseHint: "某钢厂热轧线通过在线诊断，月均异常停机从 6 次降至 3 次。",
  },
  {
    id: "cnc",
    icon: Cog,
    industry: "装备制造",
    title: "数控机床故障诊断",
    description: "主轴振动与刀具磨损实时分析，减少非计划停机，提升加工良率",
    tag: "典型",
    cluster: "离散制造",
    subtitle: "聚焦主轴、刀具、进给系统，构建加工稳定性与精度异常预警能力。",
    devices: ["数控主轴", "伺服驱动", "刀具系统", "冷却润滑单元"],
    diagnoses: ["刀具磨损", "主轴偏摆", "伺服抖动", "润滑不足"],
    dataTypes: ["振动与加速度", "主轴电流", "温升趋势", "加工参数日志"],
    benefits: ["良率提升", "换刀策略优化", "设备可用率提升", "维护工时下降"],
    caseHint: "某机加产线接入后，异常停机时长下降 28%，产品一次合格率提升 6%。",
  },
  {
    id: "power",
    icon: Zap,
    industry: "电力能源",
    title: "发电机组状态监测",
    description: "风机、汽轮机全生命周期健康评估，支持电网稳定运行",
    tag: "通用",
    cluster: "流程工业",
    subtitle: "针对风机与汽轮机关键部件，建立全生命周期健康监测与风险预警。",
    devices: ["汽轮机", "风机齿轮箱", "发电机轴承", "冷却系统"],
    diagnoses: ["轴承磨损", "齿轮异常", "温升偏移", "润滑失效"],
    dataTypes: ["振动数据", "油液指标", "温度压力", "运行工况日志"],
    benefits: ["可利用率提升", "检修窗口优化", "备件成本下降", "电网稳定性增强"],
    caseHint: "某电厂机组状态监测项目，将突发检修次数降低 35%。",
  },
  {
    id: "rail",
    icon: Train,
    industry: "轨道交通",
    title: "列车走行部故障检测",
    description: "轮对、轴承、制动系统多源数据融合分析，保障行车安全",
    tag: "典型",
    cluster: "离散制造",
    subtitle: "对轮对、轴承与制动系统进行多源融合诊断，提升运行安全与维护效率。",
    devices: ["轮对系统", "轴承箱", "制动单元", "牵引电机"],
    diagnoses: ["踏面异常", "轴承过热", "制动衰减", "振动冲击超限"],
    dataTypes: ["振动声学", "温度采样", "电流功率", "检修履历数据"],
    benefits: ["行车安全提升", "故障定位加速", "检修作业标准化", "运维成本可控"],
    caseHint: "某城轨线路上线后，走行部相关故障工单平均处理时长下降 41%。",
  },
  {
    id: "pharma",
    icon: FlaskConical,
    industry: "食品医药",
    title: "洁净生产线质量保障",
    description: "温控、压差、流量异常实时告警，满足 GMP 合规要求",
    tag: "通用",
    cluster: "离散制造",
    subtitle: "面向洁净车间与关键工艺段，保障温湿压稳定并支撑合规审计留痕。",
    devices: ["洁净空调机组", "压差控制系统", "灌装产线", "循环水系统"],
    diagnoses: ["温控偏差", "压差异常", "流量波动", "设备污染风险"],
    dataTypes: ["温湿压数据", "流量信号", "报警日志", "批次工艺记录"],
    benefits: ["合规风险降低", "批次稳定性提升", "报废率下降", "巡检效率提升"],
    caseHint: "某制药企业引入后，关键环境参数偏差告警响应时间缩短 50%。",
  },
];

export function Scenarios() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusIndex, setFocusIndex] = useState(0);
  const [panelVisible, setPanelVisible] = useState(false);
  const [panelScenario, setPanelScenario] = useState<Scenario | null>(null);

  const visibleScenarios = useMemo(() => scenarios, []);
  const [emblaRef, emblaApi] = useEmblaCarousel({
    loop: true,
    align: "center",
    skipSnaps: false,
    watchDrag: false,
  });

  const selectedScenario = useMemo(
    () => visibleScenarios.find((s) => s.id === selectedId) ?? null,
    [selectedId, visibleScenarios],
  );

  useEffect(() => {
    if (selectedId && !visibleScenarios.some((s) => s.id === selectedId)) {
      setSelectedId(null);
    }
    if (focusIndex > visibleScenarios.length - 1) {
      setFocusIndex(Math.max(0, visibleScenarios.length - 1));
    }
  }, [focusIndex, selectedId, visibleScenarios]);

  useEffect(() => {
    if (!emblaApi) return;
    const onSelect = () => {
      const idx = emblaApi.selectedScrollSnap();
      setFocusIndex(idx);
      // 仅在已打开详情面板（selectedId !== null）时，滚动同步选中态
      if (selectedId !== null) {
        const next = visibleScenarios[idx];
        if (next) setSelectedId(next.id);
      }
    };
    emblaApi.on("select", onSelect);
    onSelect();
    return () => {
      emblaApi.off("select", onSelect);
    };
  }, [emblaApi, selectedId, visibleScenarios]);

  useEffect(() => {
    if (!emblaApi || visibleScenarios.length <= 1) return;
    const timer = window.setInterval(() => {
      emblaApi.scrollNext();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [emblaApi, visibleScenarios.length]);

  useEffect(() => {
    if (!selectedScenario) {
      setPanelVisible(false);
      return;
    }
    if (!panelScenario) {
      setPanelScenario(selectedScenario);
      setPanelVisible(true);
      return;
    }
    setPanelVisible(false);
    const t = window.setTimeout(() => {
      setPanelScenario(selectedScenario);
      setPanelVisible(true);
    }, 120);
    return () => window.clearTimeout(t);
  }, [panelScenario, selectedScenario]);

  const canPrev = visibleScenarios.length > 1;
  const canNext = visibleScenarios.length > 1;

  const move = useCallback(
    (dir: -1 | 1) => {
      if (!emblaApi) return;
      if (dir === 1) emblaApi.scrollNext();
      else emblaApi.scrollPrev();
    },
    [emblaApi],
  );

  return (
    <section
      id="scenarios"
      className={`scroll-mt-24 ${ui.section}`}
      tabIndex={0}
      onMouseDown={(e) => {
        const target = e.target as HTMLElement | null;
        if (
          !target?.closest?.("[data-scenario-card]") &&
          !target?.closest?.("[data-scenario-panel]") &&
          !target?.closest?.("[data-scenario-nav]")
        ) {
          setSelectedId(null);
        }
      }}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          move(-1);
        }
        if (e.key === "ArrowRight") {
          e.preventDefault();
          move(1);
        }
      }}
    >
      <div className={ui.container}>
        <Reveal>
          <SectionDividerCue
            badge={<SectionBadge className="mb-4">适用场景</SectionBadge>}
            title={<h2 className={`${ui.titleH2} mb-4`}>映射六类检修适配场景</h2>}
            description={
              <p className={`${ui.subtitle} mx-auto max-w-2xl`}>
                保留行业覆盖视角，重点展示机泵检修、多模态检索与案例回流这类赛题适配落点
              </p>
            }
          />
        </Reveal>

        <Reveal delayMs={80}>
          <div className="relative">
          {/* 左右边缘渐隐 */}
          <div className="pointer-events-none absolute bottom-0 left-0 top-0 z-10 w-16 bg-[linear-gradient(90deg,var(--bg-main)_0%,var(--bg-main)_38%,transparent_100%)] lg:w-24" />
          <div className="pointer-events-none absolute bottom-0 right-0 top-0 z-10 w-16 bg-[linear-gradient(270deg,var(--bg-main)_0%,var(--bg-main)_38%,transparent_100%)] lg:w-24" />
          {/* 左右箭头：滚动区域两侧中部 */}
          <button
            type="button"
            data-scenario-nav
            disabled={!canPrev}
            onClick={() => move(-1)}
            className="absolute left-1 top-1/2 z-20 hidden -translate-y-1/2 rounded-full border border-border bg-card/80 p-2 text-text-secondary shadow-[0_8px_18px_rgba(15,23,42,0.07)] transition-[transform,box-shadow,border-color,color] hover:-translate-y-[52%] enabled:hover:border-brand/20 enabled:hover:text-text-primary enabled:hover:shadow-[0_12px_24px_rgba(15,23,42,0.14)] disabled:opacity-40 lg:block"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            data-scenario-nav
            disabled={!canNext}
            onClick={() => move(1)}
            className="absolute right-1 top-1/2 z-20 hidden -translate-y-1/2 rounded-full border border-border bg-card/80 p-2 text-text-secondary shadow-[0_8px_18px_rgba(15,23,42,0.07)] transition-[transform,box-shadow,border-color,color] hover:-translate-y-[52%] enabled:hover:border-brand/20 enabled:hover:text-text-primary enabled:hover:shadow-[0_12px_24px_rgba(15,23,42,0.14)] disabled:opacity-40 lg:block"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <div
            ref={emblaRef}
            className="overflow-hidden px-8 pb-2 pt-1 lg:px-16"
          >
            {/* Embla 推荐：用 padding 做间距，避免 gap + loop 造成测量抖动 */}
            <div className="flex items-stretch -ml-6 lg:-ml-8">
              {visibleScenarios.map((s, i) => {
                const Icon = s.icon;
                const isSelected = selectedScenario?.id === s.id;
                const isFocused = i === focusIndex;
                return (
                  <div
                    key={s.id}
                    data-scenario-index={i}
                    onClick={() => {
                      emblaApi?.scrollTo(i);
                      setSelectedId((prev) => (prev === s.id ? null : s.id));
                    }}
                    data-scenario-card
                    className="pl-6 lg:pl-8 shrink-0 basis-[300px] md:basis-[320px] lg:basis-[340px]"
                  >
                    {/* 外层 slide 固定宽度；内层 card 做 scale/阴影，避免 Embla loop 测量抖动与视觉重叠 */}
                    <div
                      className={cn(
                        "group relative h-[236px] w-full cursor-pointer overflow-hidden rounded-[18px] border border-border bg-card p-5 shadow-[0_8px_24px_rgba(15,23,42,0.04)]",
                        "transition-[transform,opacity,border-color,box-shadow,background-color] duration-300",
                        isSelected
                          ? "z-20 scale-[1.018] border-brand/20 bg-[linear-gradient(135deg,rgba(24,182,99,0.06),rgba(24,182,99,0.015)_62%)] shadow-[0_12px_30px_rgba(0,0,0,0.2)]"
                          : isFocused
                            ? "z-10 scale-[1.008] border-brand/12 shadow-[0_10px_24px_rgba(0,0,0,0.14)]"
                            : "z-0 opacity-70 hover:border-brand/18 hover:opacity-85",
                      )}
                    >
              {/* 顶部渐变线 */}
              <div
                className={cn(
                  "pointer-events-none absolute inset-x-0 top-0 h-px transition-opacity duration-200",
                  isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100",
                )}
                aria-hidden
                style={{ background: "linear-gradient(90deg, transparent, rgba(24,182,99,0.22), transparent)" }}
              />

              <div className="mb-4 flex items-start justify-between gap-3">
                <div
                  className={cn(
                    "flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-bg-elevated text-text-tertiary transition-colors",
                    isSelected
                      ? "border-brand/35 bg-brand/12 text-brand-dark"
                      : "group-hover:border-brand/30 group-hover:bg-brand/12 group-hover:text-brand-dark",
                  )}
                >
                  <Icon className="h-6 w-6" />
                </div>
                <span
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-[11px] font-medium",
                    s.tag === "推荐"
                      ? "border-brand/35 bg-brand/10 text-brand-dark"
                      : "border-border bg-bg-elevated text-text-secondary",
                  )}
                >
                  {s.tag}
                </span>
              </div>

              <div className="mb-1 text-xs font-medium uppercase tracking-[0.12em] text-brand/70">{s.industry}</div>
              <h3 className={cn("mb-2 text-[20px] font-semibold tracking-[-0.02em]", isSelected || isFocused ? "text-text-primary" : "text-text-secondary")}>{s.title}</h3>
              <p className="line-clamp-2 text-[14px] leading-6 text-text-secondary">{s.description}</p>

              {isSelected && (
                <div className="mt-3 flex items-center justify-end gap-1 text-[12px] font-medium text-brand/90">
                  <CircleCheck className="h-3.5 w-3.5" />
                  <span>已选中</span>
                </div>
              )}
              <div className={cn("pointer-events-none absolute inset-x-4 bottom-0 h-[2px] bg-brand/0 transition-colors", isSelected && "bg-brand/45")} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          </div>
        </Reveal>

        <Reveal delayMs={120}>
          <div className="mt-3 flex items-center justify-center gap-1.5">
          {visibleScenarios.map((s, i) => (
            <button
              key={`dot-${s.id}`}
              type="button"
              onClick={() => {
                emblaApi?.scrollTo(i);
              }}
              className={cn(
                "h-1.5 rounded-full transition-all duration-200",
                i === focusIndex ? "w-5 bg-brand/80" : "w-1.5 bg-border-strong hover:bg-brand/40",
              )}
              aria-label={`切换到场景 ${i + 1}`}
            />
          ))}
          </div>
        </Reveal>

        <Reveal delayMs={140}>
          <div
            data-scenario-panel
            className={cn(
              "mt-6 overflow-hidden rounded-[22px] border border-border-strong bg-[linear-gradient(180deg,rgba(24,182,99,0.06),rgba(24,182,99,0.02)_38%,rgba(255,255,255,0)_100%)] p-5 shadow-[0_12px_32px_rgba(15,23,42,0.08)] transition-[max-height,opacity,padding,margin] duration-300",
              selectedId ? "max-h-[1200px] opacity-100" : "max-h-0 opacity-0 p-0 mt-0 border-transparent shadow-none",
            )}
          >
          <div className="mb-4 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="mb-1 text-[12px] font-medium uppercase tracking-[0.1em] text-brand/70">
                {panelScenario?.industry ?? ""} / {panelScenario?.cluster ?? ""}
              </div>
              <h3 className="text-[24px] font-semibold tracking-[-0.02em] text-text-primary">{panelScenario?.title ?? ""}</h3>
              <p className="mt-2 text-sm leading-7 text-text-secondary">{panelScenario?.subtitle ?? ""}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2" data-scenario-nav>
              <button
                type="button"
                disabled={!canPrev}
                onClick={() => move(-1)}
                className="rounded-full border border-border bg-card p-2 text-text-secondary transition-colors enabled:hover:border-brand/25 enabled:hover:text-text-primary disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                disabled={!canNext}
                onClick={() => move(1)}
                className="rounded-full border border-border bg-card p-2 text-text-secondary transition-colors enabled:hover:border-brand/25 enabled:hover:text-text-primary disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div
            className={cn(
              "grid gap-4 transition-[opacity,transform] duration-200 sm:grid-cols-2 lg:grid-cols-5",
              panelVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1",
            )}
          >
            <InfoCol title="典型设备" items={panelScenario?.devices ?? []} />
            <InfoCol title="诊断对象" items={panelScenario?.diagnoses ?? []} />
            <InfoCol title="数据类型" items={panelScenario?.dataTypes ?? []} />
            <InfoCol title="预期收益" items={panelScenario?.benefits ?? []} />
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="mb-2 text-sm font-semibold text-text-primary">查看案例</div>
              <p className="mb-4 text-sm leading-6 text-text-secondary">{panelScenario?.caseHint ?? ""}</p>
              <div className="space-y-2">
                <button className="inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-brand px-3 py-2 text-sm font-medium text-[#04120b] transition-colors hover:bg-brand-dark">
                  查看案例
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </button>
                <button className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:border-brand/25 hover:text-text-primary">
                  查看方案详情
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
          </div>
        </Reveal>

      </div>
    </section>
  );
}

function InfoCol({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 text-sm font-semibold text-text-primary">{title}</div>
      <ul className="space-y-2 text-sm text-text-secondary">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand/70" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

