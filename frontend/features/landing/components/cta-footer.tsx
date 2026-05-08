"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { AppLogoLink } from "@/shared/components/brand/app-logo-link";
import { Button } from "@/shared/components/ui/button";
import { Reveal } from "@/shared/components/ui/reveal";
import { ROUTES, marketingEntryHref, marketingHashHref } from "@/shared/lib/routes";
import { ui } from "@/shared/theme/ui-tokens";
import { cn } from "@/shared/lib/utils";

export function CTA() {
  const pathname = usePathname();
  return (
    <section id="pricing" className="scroll-mt-24 py-24 lg:py-28">
      <div className={ui.container}>
        <Reveal>
          <div className={cn(ui.panelInteractive, "relative min-h-[280px] overflow-hidden rounded-[24px] px-8 py-12 text-center sm:px-10 lg:px-16 lg:py-14")}>
          {/* 网格纹理 */}
          <div className="cta-grid-bg pointer-events-none absolute inset-0 opacity-30" aria-hidden />
          {/* 中心径向光晕（更强） */}
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(520px_circle_at_center,rgba(24,182,99,0.18),transparent)]" aria-hidden />
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(241,244,248,0.6)_0%,rgba(255,255,255,0)_50%,rgba(241,244,248,0.6)_100%)]" aria-hidden />
          {/* 顶部渐变线 */}
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-px"
            aria-hidden
            style={{ background: "linear-gradient(90deg, transparent 0%, rgba(24,182,99,0.35) 30%, rgba(24,182,99,0.55) 50%, rgba(24,182,99,0.35) 70%, transparent 100%)" }}
          />
          <div className="relative z-10 mx-auto flex max-w-3xl flex-col items-center justify-center">
            <div className="mb-9 text-center lg:mb-10">
              <h2 className={`${ui.titleH2} mb-5 lg:text-[40px]`}>进入完整检修闭环演示</h2>
              <p className={`${ui.subtitle} mx-auto max-w-2xl`}>
                直接查看多模态知识检索、步骤化作业指引和知识回流更新如何在同一平台里完成闭环。
              </p>
            </div>

            <div className="flex flex-col justify-center gap-3 sm:flex-row sm:gap-4">
              <Button
                variant="brand"
                size="marketingLg"
                className="gap-2 bg-brand text-[#04120b] shadow-[0_14px_36px_rgba(24,182,99,0.28)] hover:bg-brand-dark hover:shadow-[0_18px_40px_rgba(24,182,99,0.34)]"
                asChild
              >
                <Link href={ROUTES.dashboard}>
                  进入系统演示
                  <ArrowRight className="h-5 w-5" />
                </Link>
              </Button>
              <Button variant="brandSecondary" size="marketingLg" className="gap-2 border-[#dde5ec] bg-card text-foreground hover:bg-bg-elevated" asChild>
                <Link href={marketingHashHref(pathname, "#metrics")}>查看能力验证</Link>
              </Button>
            </div>

            <p className="mt-7 text-sm leading-6 text-text-tertiary">推荐先看能力验证，再进入 dashboard 体验完整检修链路</p>
          </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export function Footer() {
  const pathname = usePathname();

  return (
    <footer id="docs" className="scroll-mt-24 border-t border-white/[0.08] bg-[#070d14]">
      <div className={ui.container}>
        <div className="grid gap-10 py-14 md:grid-cols-[1.3fr_1fr_1fr_1fr_1fr]">
          <div className="space-y-3">
            <AppLogoLink href={marketingEntryHref(pathname)} />
            <p className="text-sm text-[#aab6c3]">面向检修场景的多模态智能辅助与知识闭环平台</p>
            <p className="text-sm text-[#7a8695]">B/S 架构 · 可交互 Web · 多模态大模型 API</p>
            <p className="text-sm text-[#7a8695]">支持检索、步骤指引、案例回流与知识更新</p>
          </div>
          <FooterColumn title="功能导览" links={["多模态检索", "作业指引", "知识更新", "工单闭环"]} />
          <FooterColumn title="页面入口" links={["产品演示", "适用场景", "能力验证", "系统演示"]} />
          <FooterColumn title="赛题要点" links={["B/S 架构", "多模态输入", "可交互 Web", "龙架构部署"]} />
          <FooterColumn title="系统能力" links={["知识召回", "步骤预案", "结果回填", "审核发布"]} />
        </div>

        <div className="flex flex-col items-start justify-between gap-2 border-t border-white/[0.08] py-5 sm:flex-row sm:items-center">
          <p className="text-xs text-[#7a8695]">© 2026 FaultDiag · 多模态智能检修系统演示页.</p>
          <div className="flex items-center gap-5 text-xs text-[#7a8695]">
            <a href={marketingHashHref(pathname, "#overview")} className="transition-colors hover:text-[#e7edf3]">产品演示</a>
            <a href={marketingHashHref(pathname, "#metrics")} className="transition-colors hover:text-[#e7edf3]">能力验证</a>
            <a href={ROUTES.dashboard} className="transition-colors hover:text-[#e7edf3]">系统演示</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <h4 className="mb-3 text-base font-semibold text-[#e7edf3]">{title}</h4>
      <div className="space-y-2">
        {links.map((link) => (
          <a key={link} href="#" className="block text-sm text-[#7a8695] transition-colors hover:text-[#e7edf3]">
            {link}
          </a>
        ))}
      </div>
    </div>
  );
}

