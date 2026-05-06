"use client";

import { MonitorSmartphone, AppWindow, ScanSearch, Cpu } from "lucide-react";
import { ui } from "@/shared/theme/ui-tokens";

const items = [
  { icon: <MonitorSmartphone className="h-5 w-5" />, value: "B/S", label: "浏览器 + 服务器" },
  { icon: <ScanSearch className="h-5 w-5" />, value: "多模态", label: "文本 / 图片 / 型号输入" },
  { icon: <AppWindow className="h-5 w-5" />, value: "Web", label: "可交互可视化界面" },
  { icon: <Cpu className="h-5 w-5" />, value: "LoongArch", label: "支持龙架构部署要求" },
];

export function TrustStrip() {
  return (
    <section className="py-4">
      <div className={ui.container}>
        <div className="grid min-h-[84px] grid-cols-2 gap-3 rounded-2xl border border-border bg-card p-3 shadow-[0_8px_20px_rgba(15,23,42,0.04)] sm:grid-cols-4 sm:gap-0 sm:p-3">
          {items.map((item, i) => (
            <div
              key={i}
              className="flex items-center justify-center gap-3 rounded-xl border border-border/60 bg-bg-elevated px-4 py-3 sm:rounded-none sm:border-0 sm:bg-transparent sm:not-last:border-r sm:not-last:border-border"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-brand/20 bg-brand/8 text-brand-dark">
                {item.icon}
              </div>
              <div>
                <div className="text-lg font-bold tabular-nums tracking-tight text-text-primary">{item.value}</div>
                <div className="text-xs text-text-tertiary">{item.label}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

