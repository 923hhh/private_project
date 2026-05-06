"use client";

import { useMemo, useState } from "react";
import { SearchCheck, ListChecks, Network, FileCheck } from "lucide-react";
import type { ReactNode } from "react";
import { FeatureCard } from "@/shared/components/ui/feature-card";
import { Reveal } from "@/shared/components/ui/reveal";
import { SectionDividerCue } from "@/features/landing/components/section-divider-cue";
import { SectionBadge } from "@/shared/components/ui/section-badge";
import { ui } from "@/shared/theme/ui-tokens";

interface CapabilityItem {
  category: string;
  icon: ReactNode;
  title: string;
  description: string;
  points: string[];
  details: string;
  techStack: string[];
  scenarios: string[];
}

const capabilities: CapabilityItem[] = [
  {
    category: "检索层",
    icon: <SearchCheck className="h-6 w-6" />,
    title: "混合检索与跨模态匹配",
    description: "围绕文本、图片与设备型号建立统一检索入口，快速召回检修手册、案例与 SOP 片段",
    points: ["语义检索 + 关键词匹配", "图片 / 文本联合输入", "可追溯知识出处"],
    details: "基于 SSE 的事件流通道实现诊断过程实时回传，支持断链重连与状态恢复，保障现场端持续可见。",
    techStack: ["RAG", "向量检索", "跨模态匹配"],
    scenarios: ["故障图片检索", "型号过滤召回", "检修依据定位"],
  },
  {
    category: "引导层",
    icon: <ListChecks className="h-6 w-6" />,
    title: "步骤化作业引导",
    description: "将检索结果嵌入标准检修流程，自动生成可执行的工步、注意事项与合规提醒",
    points: ["步骤化操作指引", "风险提示与校验", "按等级加载流程模板"],
    details: "通过统一模型适配层按任务类型动态选择最佳模型路径，在效果、延迟与成本之间自动平衡。",
    techStack: ["流程模板", "规则校验", "步骤预案"],
    scenarios: ["标准检修流程", "应急检修提醒", "作业步骤确认"],
  },
  {
    category: "知识层",
    icon: <Network className="h-6 w-6" />,
    title: "知识关联与持续更新",
    description: "支持将案例、修订意见与检修结果回流知识库，形成关联更新和持续优化闭环",
    points: ["知识条目审核发布", "案例回填沉淀", "人工标注与修正"],
    details: "将高频时序原始数据聚合为统计摘要，减少上下文体积并保留诊断所需关键信号。",
    techStack: ["知识图谱", "案例审核", "知识更新"],
    scenarios: ["案例审核回流", "知识实时更新", "经验复用培训"],
  },
  {
    category: "工单层",
    icon: <FileCheck className="h-6 w-6" />,
    title: "工单闭环与审核发布",
    description: "从检索命中、步骤执行、结果回填到专家复核，形成完整的可追踪检修闭环",
    points: ["自动工单生成", "处理进度追踪", "审核后发布入库"],
    details: "诊断结论可直接下发工单并追踪处理状态，最终结果回写知识库形成可复用闭环资产。",
    techStack: ["工单编排", "状态机追踪", "知识沉淀"],
    scenarios: ["维修流程标准化", "多班组协同处理", "经验复用培训"],
  },
];

export function Capabilities() {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const helperCopy = useMemo(() => {
    const i = hoveredIndex ?? activeIndex ?? 0;
    const map = [
      "强调文本、图片与设备型号的统一检索入口，让检修依据召回更准、更快。",
      "强调步骤化作业引导与合规提醒，把检索结果转成可执行的检修动作。",
      "强调知识回流、案例审核与人工修正，让系统能持续积累和更新。",
      "强调工单闭环与审核发布，把每次检修都沉淀为可复用资产。",
    ];
    return map[i] ?? map[0]!;
  }, [activeIndex, hoveredIndex]);

  const focusIndex = hoveredIndex ?? activeIndex;

  return (
    <section
      id="capabilities"
      className="relative scroll-mt-24 overflow-hidden pb-20 pt-16 lg:pb-24"
      onMouseDown={(e) => {
        const target = e.target as HTMLElement | null;
        // 点击卡片以外区域：取消锁定（active）
        if (!target?.closest?.("[data-feature-card]")) {
          setActiveIndex(null);
        }
      }}
    >
      {/* 背景局部光域：跟随 hover/active */}
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 lg:opacity-100"
        aria-hidden
        style={{
          background: "none",
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        aria-hidden
        style={{
          opacity: focusIndex === null ? 0 : 1,
          background:
            focusIndex === null
              ? "none"
              : `radial-gradient(520px circle at ${(focusIndex % 4) * 25 + 12.5}% 68%, rgba(25,227,125,0.14) 0%, transparent 70%)`,
        }}
      />
      <div className={`${ui.container} relative`}>
        <Reveal>
          <SectionDividerCue
            showTopLine={false}
            badge={<SectionBadge className="mb-4">核心能力</SectionBadge>}
            title={<h2 className={`${ui.titleH2} mb-4`}>全链路智能诊断能力</h2>}
            description={
              <p className={`${ui.subtitle} mx-auto max-w-2xl transition-opacity duration-300`}>
                {helperCopy}
              </p>
            }
          />
        </Reveal>

        <div className="grid auto-rows-fr gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {capabilities.map((capability, index) => (
            <Reveal key={index} delayMs={index * 100}>
              <div className="h-full">
                <FeatureCard
                  index={index}
                  active={activeIndex === index}
                  dimmed={focusIndex !== null && focusIndex !== index}
                  onActiveChange={() => {
                    setActiveIndex((prev) => (prev === index ? null : index));
                  }}
                  onHoverChange={(hovering) => setHoveredIndex(hovering ? index : null)}
                  onActionClick={() => {
                    setActiveIndex((prev) => (prev === index ? null : index));
                  }}
                  className={index === 0 ? "h-full border-border-strong" : "h-full"}
                  actionLabel="查看能力"
                  {...capability}
                />
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

