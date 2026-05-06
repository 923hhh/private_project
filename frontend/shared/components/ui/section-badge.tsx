import * as React from "react";

import { cn } from "@/shared/lib/utils";

/** 区块眉题：中性胶囊 + 品牌小圆点 */
export function SectionBadge({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-secondary sm:px-4 sm:py-2",
        className,
      )}
    >
      <span className="h-2 w-2 shrink-0 rounded-full bg-brand shadow-[0_0_6px_var(--color-brand-glow)]" aria-hidden />
      <span>{children}</span>
    </div>
  );
}

