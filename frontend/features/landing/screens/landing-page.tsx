import { Navbar } from "@/features/landing/components/navbar";
import { Hero } from "@/features/landing/components/hero";
import { TrustStrip } from "@/features/landing/components/trust-strip";
import { ProductDemo } from "@/features/landing/components/product-demo";
import { Capabilities } from "@/features/landing/components/capabilities";
import { DiagnosisFlow } from "@/features/landing/components/diagnosis-flow";
import { ValueProps } from "@/features/landing/components/value-props";
import { Scenarios } from "@/features/landing/components/scenarios";
import { Metrics } from "@/features/landing/components/metrics";
import { CTA, Footer } from "@/features/landing/components/cta-footer";
import { Reveal } from "@/shared/components/ui/reveal";

export default function LandingPage() {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-transparent">
      <div className="pointer-events-none absolute inset-0 opacity-[0.04] [background-image:linear-gradient(to_right,rgba(255,255,255,0.07)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.07)_1px,transparent_1px)] [background-size:48px_48px]" />
      <Navbar />
      <main className="relative z-10 flex-1">
        <Reveal y={10} durationMs={650}><Hero /></Reveal>
        <Reveal delayMs={60}><TrustStrip /></Reveal>
        <Reveal delayMs={80}><ProductDemo /></Reveal>
        <Reveal delayMs={100}><Capabilities /></Reveal>
        <Reveal delayMs={120}><DiagnosisFlow /></Reveal>
        <Reveal delayMs={140}><ValueProps /></Reveal>
        <Reveal delayMs={160}><Scenarios /></Reveal>
        <Reveal delayMs={180}><Metrics /></Reveal>
        <Reveal delayMs={200}><CTA /></Reveal>
      </main>
      <Footer />
    </div>
  );
}

