/**
 * Landing 页面统一布局与排版 token
 */
export const ui = {
  container: "mx-auto w-full max-w-[1260px] px-5 lg:px-7",
  section: "py-14 lg:py-16",
  sectionHeader: "mb-8 text-center lg:mb-10",
  panel: "rounded-[20px] border border-border bg-card shadow-[0_8px_24px_rgba(15,23,42,0.04)]",
  panelInteractive:
    "rounded-[24px] border border-border bg-card shadow-[0_8px_24px_rgba(15,23,42,0.04)] transition-[border-color,box-shadow,transform] duration-200 hover:border-brand/35 hover:shadow-[0_12px_30px_rgba(15,23,42,0.06)] hover:-translate-y-0.5",
  card:
    "rounded-[18px] border border-border bg-card shadow-[0_8px_24px_rgba(15,23,42,0.04)] transition-[border-color,box-shadow,transform] duration-200 hover:border-brand/35 hover:bg-brand/4 hover:shadow-[0_12px_30px_rgba(15,23,42,0.06)] hover:-translate-y-0.5",
  badge:
    "inline-flex items-center gap-2 rounded-full border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-secondary sm:px-4 sm:py-2",
  eyebrowDot: "h-2 w-2 shrink-0 rounded-full bg-brand",
  titleH1: "text-4xl font-bold tracking-[-0.04em] text-text-primary sm:text-5xl lg:text-[64px]",
  titleH2: "text-[32px] font-bold tracking-[-0.03em] text-text-primary sm:text-4xl lg:text-[44px]",
  titleH3: "text-2xl font-bold tracking-[-0.03em] text-text-primary sm:text-3xl",
  subtitle: "text-[15px] leading-7 text-text-secondary lg:text-base",
} as const;
