import Link from "next/link";

import { cn } from "@/shared/lib/utils";

type AppLogoLinkProps = {
  href: string;
  className?: string;
  title?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
};

/**
 * 全站统一品牌标识：沿用 landing 页 Logo 视觉
 */
export function AppLogoLink({ href, className, title, onClick }: AppLogoLinkProps) {
  return (
    <Link
      href={href}
      title={title}
      onClick={onClick}
      className={cn(
        "group flex items-center gap-2 rounded-md outline-none transition-transform duration-200 ease-out hover:-translate-y-[1px] active:translate-y-0 focus-visible:ring-2 focus-visible:ring-brand/40",
        className,
      )}
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-brand/20 bg-brand/10 shadow-[0_0_0_0_rgba(34,197,94,0),0_0_0_0_rgba(34,197,94,0)] transition-all duration-200 ease-out group-hover:scale-[1.03] group-hover:border-brand/35 group-hover:bg-brand/15 group-hover:shadow-[0_0_0_4px_rgba(34,197,94,0.08),0_8px_20px_rgba(34,197,94,0.16)] group-active:scale-[0.98] dark:border-white/[0.08] dark:bg-white/[0.04] dark:group-hover:border-[#19e37d]/40 dark:group-hover:bg-[#19e37d]/12 dark:group-hover:shadow-[0_0_0_4px_rgba(25,227,125,0.10),0_8px_20px_rgba(25,227,125,0.18)]">
        <span className="text-sm font-bold text-brand-dark dark:text-[#19e37d]">FD</span>
      </div>
      <span className="text-lg font-semibold text-text-primary transition-colors duration-200 ease-out group-hover:text-[#0b1220] dark:text-[#f5f7fa] dark:group-hover:text-white">
        FaultDiag
      </span>
    </Link>
  );
}

