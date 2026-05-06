import { cn } from "@/shared/lib/utils";

export type MetricProps = {
  value: string;
  label: string;
  description?: string;
  /** 全表唯一高亮指标（其余为灰阶数字） */
  featured?: boolean;
  className?: string;
};

export function Metric({ value, label, description, featured, className }: MetricProps) {
  return (
    <div
      className={cn(
        "relative flex min-h-[160px] flex-col items-center justify-center overflow-hidden px-6 py-8 text-center transition-colors duration-200 sm:min-h-[180px] lg:px-8 lg:py-10",
        featured && "metric-featured-glow",
        className,
      )}
    >
      {featured && (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          aria-hidden
          style={{ background: "linear-gradient(90deg, transparent, rgba(24,182,99,0.45), transparent)" }}
        />
      )}
      <div
        className={cn(
          "text-4xl font-semibold tracking-[-0.05em] sm:text-[46px] lg:text-[52px]",
          featured
            ? "gradient-number"
            : "text-text-primary",
        )}
      >
        {value}
      </div>
      <div className="mt-3 text-base font-medium text-text-primary sm:text-lg">{label}</div>
      {description ? (
        <div className="mt-2 max-w-[220px] text-sm leading-6 text-text-secondary">{description}</div>
      ) : null}
    </div>
  );
}

