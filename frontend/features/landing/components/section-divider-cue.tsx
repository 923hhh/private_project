"use client";

import type { ReactNode } from "react";

import { cn } from "@/shared/lib/utils";

type SectionDividerCueProps = {
  badge: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  className?: string;
  showTopLine?: boolean;
  showBottomLine?: boolean;
};

export function SectionDividerCue({
  badge,
  title,
  description,
  className,
}: SectionDividerCueProps) {
  return (
    <div className={cn("mb-8 text-center lg:mb-10", className)}>
      <div className="mx-auto w-full max-w-3xl">
        {badge}
        {title}
        {description}
      </div>
    </div>
  );
}

