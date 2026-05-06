"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/shared/lib/utils";

type RevealProps = {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  durationMs?: number;
  y?: number;
  threshold?: number;
  once?: boolean;
};

export function Reveal({
  children,
  className,
  delayMs = 0,
  durationMs = 700,
  y = 20,
  threshold = 0.2,
  once = true,
}: RevealProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduceMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const node = ref.current;
    if (!node || reduceMotion) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;
        setVisible(true);
        if (once) observer.unobserve(node);
      },
      { threshold },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [once, reduceMotion, threshold]);

  return (
    <div
      ref={ref}
      className={cn("transition-[opacity,transform] will-change-transform", className)}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : `translateY(${y}px)`,
        transitionDuration: `${durationMs}ms`,
        transitionDelay: `${delayMs}ms`,
        transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
      }}
    >
      {children}
    </div>
  );
}


