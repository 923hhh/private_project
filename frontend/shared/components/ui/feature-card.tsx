import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";

import { cn } from "@/shared/lib/utils";

export type FeatureCardProps = {
  category?: string;
  icon: ReactNode;
  title: string;
  description: string;
  points: string[];
  /** 首卡主视觉：淡绿底边，其余为中性卡 */
  featured?: boolean;
  index?: number;
  active?: boolean;
  dimmed?: boolean;
  onActiveChange?: () => void;
  onHoverChange?: (hovering: boolean) => void;
  onActionClick?: () => void;
  actionLabel?: string;
  className?: string;
};

export function FeatureCard({
  category,
  icon,
  title,
  description,
  points,
  featured = false,
  index,
  active,
  dimmed,
  onActiveChange,
  onHoverChange,
  onActionClick,
  actionLabel = "查看详情",
  className,
}: FeatureCardProps) {
  return (
    <div
      className={cn(
        "card-top-gradient group relative flex min-h-[250px] flex-col rounded-[20px] border border-border bg-card p-6 shadow-[0_8px_24px_rgba(15,23,42,0.04)] transition-[box-shadow,border-color,background-color,opacity,filter] duration-250 ease-out sm:min-h-[260px]",
        "hover:border-brand/35 hover:bg-[linear-gradient(135deg,rgba(25,227,125,0.08),rgba(25,227,125,0.02)_60%)] hover:shadow-[0_14px_36px_rgba(0,0,0,0.24)]",
        active && "border-brand/40 shadow-[0_14px_36px_rgba(0,0,0,0.26)]",
        dimmed && "opacity-70 saturate-[0.92]",
        className,
      )}
      data-feature-card
      role={onActiveChange ? "button" : undefined}
      tabIndex={onActiveChange ? 0 : undefined}
      onClick={(e) => {
        e.stopPropagation();
        onActiveChange?.();
      }}
      onKeyDown={(e) => {
        if (!onActiveChange) return;
        if (e.key === "Enter" || e.key === " ") onActiveChange();
      }}
      onMouseEnter={() => onHoverChange?.(true)}
      onMouseLeave={() => onHoverChange?.(false)}
    >
      {/* active 底部光条 */}
      <div
        className={cn(
          "pointer-events-none absolute inset-x-6 bottom-4 h-px opacity-0 transition-opacity duration-200",
          active && "opacity-100",
        )}
        aria-hidden
        style={{ background: "linear-gradient(90deg, transparent, rgba(25,227,125,0.55), transparent)" }}
      />

      <div className="mb-4 flex items-center justify-between">
        <div
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-bg-elevated text-text-tertiary transition-[border-color,background-color,box-shadow,transform,color] duration-200",
            "group-hover:border-brand/35 group-hover:bg-brand/12 group-hover:text-brand-dark group-hover:shadow-[0_0_0_6px_rgba(25,227,125,0.10)]",
            active && "border-brand/35 bg-brand/14 text-brand-dark shadow-[0_0_0_6px_rgba(25,227,125,0.12)]",
          )}
        >
          {icon}
        </div>
        {index !== undefined && (
          <span
            className={cn(
              "card-index-badge transition-[border-color,background-color,color,box-shadow] duration-200",
              (active || featured) && "border-brand/40 bg-brand/12 text-brand-light shadow-[0_0_0_6px_rgba(25,227,125,0.10)]",
              !active && "group-hover:border-brand/35 group-hover:bg-brand/10 group-hover:text-brand-light",
            )}
          >
            0{index + 1}
          </span>
        )}
      </div>
      {category ? (
        <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.1em] text-brand/70">{category}</div>
      ) : null}
      <h3 className="text-lg font-semibold tracking-[-0.02em] text-text-primary sm:text-xl">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary sm:text-[15px]">{description}</p>

      {/* 默认收起：hover/active 才 reveal */}
      <div className="mt-auto pt-3">
        <ul
          className={cn(
            "space-y-2 text-sm text-text-primary transition-[opacity,transform] duration-250 ease-out",
            "opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0",
            active && "opacity-100 translate-y-0",
          )}
        >
          {points.map((point) => (
            <li key={point} className="flex items-start gap-2.5">
              <span
                className={cn(
                  "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                  featured ? "bg-brand/80" : "bg-text-tertiary/50 group-hover:bg-brand/60",
                  active && "bg-brand/70",
                )}
              />
              <span className="text-text-secondary">{point}</span>
            </li>
          ))}
        </ul>

        {/* 二级入口：hover/active 出现 */}
        <div
          className={cn(
            "mt-3 flex items-center justify-end text-[13px] font-medium text-brand/80 transition-[opacity,transform] duration-200",
            "opacity-0 translate-y-1 group-hover:opacity-100 group-hover:translate-y-0",
            active && "opacity-100 translate-y-0",
          )}
        >
          <button
            type="button"
            className="inline-flex translate-x-2 translate-y-2 items-center gap-1.5 rounded px-1 py-0.5 text-brand/80 transition-[transform,color,opacity] duration-200 group-hover:translate-x-0 group-hover:translate-y-0 hover:text-brand-light"
            onClick={(e) => {
              e.stopPropagation();
              onActionClick?.();
            }}
          >
            <span>{actionLabel}</span>
            <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

