"use client";

import { useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";
import { createPortal } from "react-dom";

const SCROLL_THRESHOLD = 500;

export function BackToTopButton() {
  const [visible, setVisible] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleMotionChange = () => setReduceMotion(media.matches);
    handleMotionChange();

    const handleScroll = () => {
      setVisible(window.scrollY > SCROLL_THRESHOLD);
    };
    handleScroll();

    media.addEventListener("change", handleMotionChange);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      media.removeEventListener("change", handleMotionChange);
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  const handleBackToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: reduceMotion ? "auto" : "smooth",
    });
  };

  if (!mounted) return null;

  return createPortal(
    <button
      type="button"
      aria-label="返回顶部"
      onClick={handleBackToTop}
      className={[
        "fixed bottom-5 right-5 z-40 h-11 w-11 rounded-full",
        "border border-emerald-400/45 bg-[#0b1118]/70 text-emerald-300",
        "backdrop-blur-md",
        "sm:bottom-6 sm:right-6",
        "hover:-translate-y-0.5 hover:border-emerald-300/70 hover:text-emerald-200",
        "hover:shadow-[0_0_16px_rgba(16,185,129,0.35)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-[#090c11]",
        reduceMotion ? "" : "transition-all duration-300 ease-out",
        visible ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
      ].join(" ")}
    >
      <ArrowUp className="mx-auto h-5 w-5" />
    </button>,
    document.body,
  );
}

