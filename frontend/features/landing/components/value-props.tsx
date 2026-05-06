"use client";

import { TrendingDown, Zap, BookOpen } from "lucide-react";
import type { ReactNode } from "react";

import { Reveal } from "@/shared/components/ui/reveal";
import { SectionDividerCue } from "@/features/landing/components/section-divider-cue";
import { SectionBadge } from "@/shared/components/ui/section-badge";
import { ui } from "@/shared/theme/ui-tokens";
import { cn } from "@/shared/lib/utils";

interface ValueCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  highlight: string;
  highlightLabel: string;
  features: string[];
  cardIndex: number;
}

function ValueCard({ icon, title, description, highlight, highlightLabel, features, cardIndex }: ValueCardProps) {
  const bulletAccent = (index: number) =>
    cardIndex === 0 ? index < 2 : index === 0;

  return (
    <div className={cn(ui.card, "group relative min-h-[220px] overflow-hidden p-7 lg:p-8")}>
      {/* 左侧品牌竖线 */}
      <div
        className="pointer-events-none absolute inset-y-0 left-0 w-px opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        aria-hidden
        style={{ background: "linear-gradient(180deg, transparent 0%, rgba(24,182,99,0.45) 40%, rgba(24,182,99,0.45) 60%, transparent 100%)" }}
      />
      {/* 顶部渐变线 */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        aria-hidden
        style={{ background: "linear-gradient(90deg, transparent, rgba(24,182,99,0.24), transparent)" }}
      />

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Left content */}
        <div className="flex-[0_0_68%]">
          <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-xl border border-brand/20 bg-brand/8 transition-colors group-hover:border-brand/25 group-hover:bg-brand/12">
            <div className="text-brand-dark">{icon}</div>
          </div>

          <h3 className="mb-2 text-[22px] font-semibold text-text-primary">{title}</h3>
          <p className="mb-5 text-sm leading-7 text-text-secondary">{description}</p>

          <ul className="space-y-3">
            {features.map((feature, index) => (
              <li key={index} className="flex items-start gap-3">
                <div
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${bulletAccent(index) ? "bg-brand/8" : "bg-bg-elevated"
                    }`}
                >
                  <div
                    className={`h-1.5 w-1.5 rounded-full ${bulletAccent(index) ? "bg-brand" : "bg-text-tertiary/70"
                      }`}
                  />
                </div>
                <span className="text-sm text-text-secondary">{feature}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* 右侧指标 */}
        <div className="flex w-full flex-[0_0_32%] flex-col items-center justify-center rounded-xl border border-border bg-[#f7faf8] px-4 py-8 text-center shadow-[0_8px_20px_rgba(15,23,42,0.08)] dark:border-white/[0.08] dark:bg-[#101a27] dark:shadow-[0_10px_28px_rgba(0,0,0,0.28)] lg:max-w-[220px] lg:py-10">
          <div className="gradient-number text-[54px] font-semibold leading-none tracking-[-0.04em]">
            {highlight}
          </div>
          <div className="mt-3 max-w-[12rem] text-sm leading-snug text-text-secondary dark:text-[#8fa1b7]">{highlightLabel}</div>
        </div>
      </div>
    </div>
  );
}

const valueProps: Omit<ValueCardProps, "cardIndex">[] = [
  {
    icon: <TrendingDown className="w-7 h-7" />,
    title: "多模态知识检索功能",
    description: "支持输入文本、故障图片和设备型号，结合语义检索与跨模态匹配，快速调取检修手册与案例资源。",
    highlight: "跨模态",
    highlightLabel: "文本 / 图片 / 型号联合匹配",
    features: [
      "语义检索与模糊匹配结合",
      "知识出处可追溯展示",
      "支持多类型输入统一检索",
    ],
  },
  {
    icon: <Zap className="w-7 h-7" />,
    title: "标准化作业指引功能",
    description: "将检索结果接入检修全流程，生成分步骤操作建议、风险与合规提醒，并按设备类型推送执行预案。",
    highlight: "步骤化",
    highlightLabel: "检修步骤预案与合规提醒",
    features: [
      "嵌入标准检修流程",
      "高危步骤风险提示",
      "支持个性化流程推送",
    ],
  },
  {
    icon: <BookOpen className="w-7 h-7" />,
    title: "知识沉淀与更新功能",
    description: "支持上传检修案例与经验总结，审核后纳入知识条目，并通过人工标注与修订持续优化系统适配性。",
    highlight: "可更新",
    highlightLabel: "案例回流、审核发布、持续修正",
    features: [
      "检修案例沉淀入库",
      "审核发布与回滚管理",
      "人工标注修正模型输出",
    ],
  },
];

export function ValueProps() {
  return (
    <section id="value" className={`scroll-mt-24 ${ui.section}`}>
      <div className={ui.container}>
        <Reveal>
          <SectionDividerCue
            badge={<SectionBadge className="mb-4">核心功能</SectionBadge>}
            title={<h2 className={`${ui.titleH2} mb-4`}>围绕赛题要求构建三项核心能力</h2>}
            description={
              <p className={`${ui.subtitle} mx-auto max-w-2xl`}>
                保留产品化观感，但把多模态检索、作业指引和知识更新三条能力线说清楚
              </p>
            }
          />
        </Reveal>

        <div className="space-y-6">
          {valueProps.map((prop, index) => (
            <Reveal key={index} delayMs={index * 100}>
              <ValueCard cardIndex={index} {...prop} />
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

