"use client";

import { useEffect, useState } from "react";
import { Database, AlertTriangle, Search, FileText, ClipboardCheck } from "lucide-react";
import { SectionDividerCue } from "@/features/landing/components/section-divider-cue";
import { SectionBadge } from "@/shared/components/ui/section-badge";
import { ui } from "@/shared/theme/ui-tokens";

const steps = [
  {
    icon: <Database className="h-6 w-6" />,
    title: "输入问题",
    descriptionLines: ["支持文本、图片", "与设备型号输入"],
    guide: "先收集故障描述、现场图片与设备上下文，构建可检索的问题入口。",
    bullets: ["文本提问", "故障图片上传", "设备型号绑定"],
  },
  {
    icon: <AlertTriangle className="h-6 w-6" />,
    title: "检索知识",
    descriptionLines: ["召回检修手册、", "SOP 与历史案例"],
    guide: "通过语义检索与跨模态匹配定位最相关的检修依据与步骤片段。",
    bullets: ["手册片段召回", "跨模态匹配", "知识出处可追溯"],
  },
  {
    icon: <Search className="h-6 w-6" />,
    title: "生成指引",
    descriptionLines: ["自动生成步骤化", "作业预案"],
    guide: "根据命中的知识依据生成标准化作业指引、风险提示与执行建议。",
    bullets: ["步骤化预案", "合规提醒", "关键风险标注"],
  },
  {
    icon: <FileText className="h-6 w-6" />,
    title: "回填结果",
    descriptionLines: ["记录检修结论、", "附件与处理说明"],
    guide: "执行结束后回填检修结果、现场凭证和补充说明，形成结构化留痕。",
    bullets: ["结构化回填", "附件凭证上传", "结论说明归档"],
  },
  {
    icon: <ClipboardCheck className="h-6 w-6" />,
    title: "审核更新",
    descriptionLines: ["审核发布并更新", "知识条目"],
    guide: "专家复核后发布候选知识，将案例与修订意见纳入持续更新闭环。",
    bullets: ["专家审核发布", "知识条目更新", "案例持续沉淀"],
  },
];

export function DiagnosisFlow() {
  const [activeStep, setActiveStep] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return;
    const timer = window.setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [isPaused]);

  return (
    <section id="workflow" className={`scroll-mt-24 ${ui.section}`}>
      <div className={ui.container}>
        <SectionDividerCue
          badge={<SectionBadge className="mb-4">诊断流程</SectionBadge>}
          title={<h2 className={`${ui.titleH2} mb-4`}>5 步完成智能检修闭环</h2>}
          description={
            <p className={`${ui.subtitle} mx-auto max-w-2xl transition-opacity duration-300`}>
              {steps[activeStep]?.guide}
            </p>
          }
        />

        <div
          className="relative"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
        >
          <div
            className="pointer-events-none absolute left-[6%] right-[6%] top-7 hidden h-[1.5px] rounded-full bg-[rgba(255,255,255,0.2)] lg:block"
            aria-hidden
          />
          <div className="pointer-events-none absolute left-[6%] right-[6%] top-7 hidden h-[1.5px] lg:block" aria-hidden>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(activeStep / (steps.length - 1)) * 100}%`,
                background:
                  "linear-gradient(90deg, rgba(16,185,129,0.45), rgba(16,185,129,0.65), rgba(16,185,129,0.55))",
              }}
            />
          </div>
          <div className="pointer-events-none absolute left-[6%] right-[6%] top-7 hidden h-[1.5px] lg:block" aria-hidden>
            <div
              className="absolute top-1/2 h-4 w-14 -translate-y-1/2 -translate-x-1/2 rounded-full bg-[rgba(16,185,129,0.22)] blur-sm transition-all duration-500"
              style={{
                left: `${(activeStep / (steps.length - 1)) * 100}%`,
              }}
            />
          </div>

          <div className="grid gap-x-4 gap-y-4 sm:grid-cols-2 lg:grid-cols-5">
            {steps.map((step, i) => {
              const isActive = activeStep === i;
              const isDone = i < activeStep;
              const isUpcoming = i > activeStep;
              const distance = Math.abs(activeStep - i);
              return (
                <div
                  key={i}
                  className={`group relative flex flex-col items-center text-center transition-[opacity,transform,filter] duration-500 ${
                    isUpcoming ? "opacity-72" : "opacity-100"
                  } ${distance === 0 ? "z-10" : distance === 1 ? "z-[2]" : "z-[1]"}`}
                  onMouseEnter={() => {
                    setActiveStep(i);
                    setIsPaused(true);
                  }}
                  onClick={() => {
                    setActiveStep(i);
                    setIsPaused(true);
                  }}
                >
                  <div
                    className={`relative z-10 mb-4 flex h-[56px] w-[56px] items-center justify-center rounded-full border bg-card shadow-[0_8px_20px_rgba(15,23,42,0.05)] transition-all duration-300 ${
                      isDone
                        ? "border-brand/35 bg-brand/8"
                        : isActive
                          ? "border-brand/50 bg-brand/14 shadow-[0_10px_24px_rgba(24,195,126,0.16)]"
                          : "border-border bg-card"
                    }`}
                  >
                    {isActive && (
                      <span className="pointer-events-none absolute inset-0 rounded-full border border-brand/40">
                        <span className="absolute inset-0 rounded-full bg-brand/20 animate-ping" />
                      </span>
                    )}
                    <div className={`transition-colors ${isDone ? "text-brand/85" : isActive ? "text-brand" : "text-text-tertiary"}`}>
                      {step.icon}
                    </div>
                    <span
                      className={`absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full border bg-bg-main text-[9px] font-bold ${
                        isActive
                          ? "border-brand/50 text-brand"
                          : isDone
                            ? "border-brand/35 text-brand/85"
                            : "border-border text-text-tertiary"
                      }`}
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </div>

                  <div
                    className={`relative min-h-[196px] w-full overflow-hidden rounded-[18px] border border-border bg-card px-4 py-5 shadow-[0_8px_24px_rgba(15,23,42,0.04)] transition-[transform,opacity,border-color,box-shadow,background-color,filter] duration-400 ease-out sm:min-h-[188px] lg:min-h-[208px] ${
                      isActive
                        ? "scale-[1.03] pointer-events-none border-brand/35 bg-brand/6 shadow-[0_12px_30px_rgba(15,23,42,0.10)]"
                        : isDone
                          ? "scale-[0.99] border-brand/20 bg-[rgba(24,182,99,0.03)] opacity-95"
                        : distance === 1
                          ? "scale-[0.985] opacity-88"
                          : "scale-[0.97] opacity-78"
                    }`}
                  >
                    <h3 className="mb-2 text-base font-semibold text-text-primary">{step.title}</h3>
                    <p className="mx-auto flex max-w-[13ch] flex-col text-sm leading-6 text-text-secondary">
                      {step.descriptionLines.map((line) => (
                        <span key={line}>{line}</span>
                      ))}
                    </p>
                    <ul
                      className={`mt-3 space-y-1.5 overflow-hidden text-left text-xs leading-5 text-text-secondary transition-all duration-250 ${
                        isActive ? "max-h-24 opacity-100" : "max-h-0 opacity-0"
                      }`}
                    >
                      {step.bullets.map((b) => (
                        <li key={b} className="flex items-start gap-1.5">
                          <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-brand/70" />
                          <span>{b}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

