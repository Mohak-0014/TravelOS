"use client";

import { useRef } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform } from "framer-motion";
import {
  ArrowRight,
  Compass,
  MapPin,
  Hotel,
  Wallet,
  Ticket,
  CloudSun,
  CheckCircle2,
  Brain,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { RouteDash } from "@/components/ui/RouteDash";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Globe } from "@/components/ui/Globe";
import { TiltCard } from "@/components/ui/TiltCard";
import { DestinationScroll, DESTINATIONS } from "@/components/travel/DestinationScroll";
import { fadeUp, stagger, viewportOnce, wordReveal, EASE } from "@/lib/motion";

// ── Hero photography ──────────────────────────────────────────────────────────
// Public Unsplash CDN. The hero paints a midnight gradient underneath, so a
// slow connection (or offline dev) shows a designed fallback, never a hole.

const HERO_PHOTO = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?q=80&w=2400&auto=format&fit=crop";

// ── Agent pipeline data ───────────────────────────────────────────────────────

const AGENTS: { name: string; desc: string; icon: LucideIcon }[] = [
  { name: "Travel Style", desc: "Learns your pace, taste, and style", icon: Compass },
  { name: "Itinerary", desc: "Clusters attractions into walkable zones", icon: MapPin },
  { name: "Hotel Agent", desc: "Ranks hotels by your luxury tier and budget", icon: Hotel },
  { name: "Budget", desc: "Catches overspend. Suggests upgrades.", icon: Wallet },
  { name: "Local Events", desc: "Finds what's on during your trip", icon: Ticket },
  { name: "Weather", desc: "Replans around rain before you notice", icon: CloudSun },
  { name: "Approval Gate", desc: "You review, you decide — AI proposes, not imposes", icon: CheckCircle2 },
  { name: "Memory", desc: "Every trip makes the next one better", icon: Brain },
];

// ── Feature highlights ────────────────────────────────────────────────────────

const FEATURES: { title: string; desc: string; icon: LucideIcon }[] = [
  {
    title: "Personalization",
    desc: "Remembers you love rooftop bars. Knows you hate museums before noon. Gets sharper with every trip.",
    icon: Brain,
  },
  {
    title: "Live Adaptation",
    desc: "Rain forecast on Day 3? We've already moved the outdoor activity indoors. No notification needed.",
    icon: CloudSun,
  },
  {
    title: "Budget Intelligence",
    desc: "Over by 22%? Here's what to swap. Under by 30%? Here's an upgrade that fits perfectly.",
    icon: Wallet,
  },
];

const GLOBE_MARKERS = DESTINATIONS.map((d) => {
  const [lat, lng] = d.coords.split(" ").map((part) => {
    const sign = part.includes("S") || part.includes("W") ? -1 : 1;
    return sign * parseFloat(part);
  });
  return { location: [lat, lng] as [number, number], size: 0.1 };
});

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

// Masked word-by-word reveal for the hero headline.
function RevealWords({ text, className }: { text: string; className?: string }) {
  return (
    <span className={className}>
      {text.split(" ").map((word, i) => (
        <span key={i} className="inline-block overflow-hidden align-bottom pb-[0.12em] -mb-[0.12em]">
          <motion.span variants={wordReveal} className="inline-block">
            {word}
          </motion.span>
          {" "}
        </span>
      ))}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  // Photo drifts slower than the page; content drifts up and fades — classic cinematic parallax.
  const photoY = useTransform(scrollYProgress, [0, 1], ["0%", "18%"]);
  const contentY = useTransform(scrollYProgress, [0, 1], ["0%", "-12%"]);
  const contentOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

  return (
    <div className="relative bg-paper">
      {/* ════════════════ HERO — full-bleed cinematic ════════════════ */}
      <section ref={heroRef} className="relative h-[100svh] min-h-[640px] overflow-hidden">
        {/* Fallback: midnight sky with a warm horizon ember — visible until the photo paints */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 65% at 50% 100%, rgba(255,125,80,0.22) 0%, rgba(255,125,80,0.05) 35%, transparent 60%), linear-gradient(180deg, #0B0F14 0%, #101825 55%, #1A1E28 100%)",
          }}
        />
        {/* Photo layer — Ken Burns drift + scroll parallax */}
        <motion.div style={{ y: photoY }} className="absolute inset-[-6%]">
          <div className="absolute inset-0 kenburns bg-cover bg-center" style={{ backgroundImage: `url(${HERO_PHOTO})` }} />
        </motion.div>
        {/* Scrims: darken for legibility, then dissolve into the page background */}
        <div className="absolute inset-0 bg-black/35" />
        <div className="absolute inset-x-0 bottom-0 h-64 bg-fade-b" />
        <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-black/50 to-transparent" />

        {/* Floating mono coordinates — quiet atlas details in the corners */}
        <span className="hidden md:block absolute top-24 left-8 font-mono text-[10px] tracking-widest text-white/35 z-10">
          27.99°N 86.93°E
        </span>
        <span className="hidden md:block absolute bottom-28 right-8 font-mono text-[10px] tracking-widest text-white/35 z-10">
          ALT 8,848M · FL360
        </span>

        {/* Content */}
        <motion.div
          style={{ y: contentY, opacity: contentOpacity }}
          className="relative z-10 h-full flex flex-col items-center justify-center px-4 text-center"
        >
          <motion.div variants={stagger(0.12)} initial="hidden" animate="show" className="max-w-4xl mx-auto">
            <motion.div variants={fadeUp} className="mb-8">
              <span className="glass inline-flex items-center gap-2 font-mono text-[11px] font-medium px-4 py-2 rounded-full text-white/85 uppercase tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                AI-Powered · Always Learning
              </span>
            </motion.div>

            <h1 className="font-display text-5xl md:text-7xl lg:text-8xl font-medium leading-[1.02] tracking-tight text-white mb-8">
              <RevealWords text="Where to" />
              <span className="inline-block overflow-hidden align-bottom pb-[0.12em] -mb-[0.12em] pr-[0.1em]">
                <motion.span variants={wordReveal} className="inline-block italic text-sunset pr-[0.06em]">
                  next?
                </motion.span>
              </span>
              <br />
              <RevealWords text="We'll handle the rest." />
            </h1>

            <motion.p variants={fadeUp} className="text-lg md:text-xl text-white/75 mb-10 max-w-2xl mx-auto leading-relaxed">
              Tell us where. Eight AI agents plan every detail — <span className="text-white font-medium">and get smarter every trip.</span>
            </motion.p>

            <motion.div variants={fadeUp} className="mb-12">
              <RouteDash from="HERE" to="ANYWHERE" arc className="max-w-xs mx-auto [&_span]:text-white/60" />
            </motion.div>

            <motion.div variants={fadeUp} className="flex items-center justify-center gap-4 flex-wrap">
              <Link href="/login">
                <Button size="lg" iconRight={ArrowRight}>
                  Start Planning
                </Button>
              </Link>
              <Button
                variant="ghost"
                size="lg"
                onClick={() => scrollToSection("how-it-works")}
                className="text-white/80 hover:text-white hover:bg-white/10"
              >
                See how it works
              </Button>
            </motion.div>
          </motion.div>
        </motion.div>

        {/* Scroll cue */}
        <motion.button
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.6, duration: 0.8 }}
          onClick={() => scrollToSection("how-it-works")}
          className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-1.5 text-white/50 hover:text-white/90 transition-colors"
          aria-label="Scroll down"
        >
          <span className="font-mono text-[10px] uppercase tracking-[0.25em]">Scroll</span>
          <motion.span animate={{ y: [0, 5, 0] }} transition={{ repeat: Infinity, duration: 1.8, ease: "easeInOut" }}>
            <ChevronDown className="w-4 h-4" />
          </motion.span>
        </motion.button>
      </section>

      {/* ════════════════ MARQUEE — kinetic destination ticker ════════════════ */}
      <section className="relative py-6 border-y border-ink-900/10 overflow-hidden" aria-hidden="true">
        <div className="flex w-max animate-marquee gap-12">
          {[...DESTINATIONS, ...DESTINATIONS].map((d, i) => (
            <span key={`${d.id}-${i}`} className="flex items-center gap-12 shrink-0">
              <span className="font-display italic text-xl text-ink-600">{d.name}</span>
              <span className="font-mono text-[10px] tracking-widest text-ink-300">{d.coords}</span>
              <span className="w-1 h-1 rounded-full bg-accent/60" />
            </span>
          ))}
        </div>
      </section>

      {/* ════════════════ HOW IT WORKS ════════════════ */}
      <section id="how-it-works" className="relative py-28 px-4">
        <div className="max-w-3xl mx-auto">
          <motion.div initial="hidden" whileInView="show" viewport={viewportOnce} variants={fadeUp} className="mb-14">
            <SectionHeader eyebrow="The Itinerary Engine" />
            <h2 className="font-display text-4xl md:text-5xl font-medium text-ink-900 mb-4">
              8 Agents. <span className="italic text-sunset">One perfect trip.</span>
            </h2>
            <p className="text-ink-400 text-lg max-w-xl">
              Your trip runs through a pipeline of specialised AI agents, each optimising a different dimension.
            </p>
          </motion.div>

          <motion.div initial="hidden" whileInView="show" viewport={viewportOnce} variants={stagger(0.06)}>
            {AGENTS.map((agent, i) => (
              <motion.div
                key={agent.name}
                variants={fadeUp}
                className="group flex items-start gap-5 py-5 border-t border-ink-900/10 last:border-b px-3 -mx-3 rounded-lg hover:bg-surface transition-colors duration-200"
              >
                <span className="font-mono text-xs text-ink-300 group-hover:text-accent transition-colors pt-1 w-6 shrink-0">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="w-9 h-9 rounded-lg bg-accent-tint border border-accent/20 flex items-center justify-center shrink-0 group-hover:shadow-glow transition-shadow duration-300">
                  <agent.icon className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <p className="font-medium text-ink-900">{agent.name}</p>
                  <p className="text-sm text-ink-400 mt-0.5">{agent.desc}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ════════════════ DESTINATION SHOWCASE (photo cards, 3D tilt) ════════════════ */}
      <section className="relative py-24 border-t border-ink-900/10 overflow-hidden">
        <div className="max-w-5xl mx-auto px-4 text-center mb-12">
          <motion.div initial="hidden" whileInView="show" viewport={viewportOnce} variants={fadeUp}>
            <SectionHeader eyebrow="Plan Anywhere" />
            <h2 className="font-display text-3xl md:text-5xl font-medium text-ink-900">
              Where will you go <span className="italic text-sunset">first?</span>
            </h2>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={viewportOnce}
          transition={{ duration: 0.6 }}
          className="max-w-5xl mx-auto"
        >
          <DestinationScroll />
        </motion.div>
        <p className="text-center font-mono text-xs text-ink-300 mt-3">← scroll or drag →</p>
      </section>

      {/* ════════════════ INTERACTIVE GLOBE ════════════════ */}
      <section className="relative py-28 px-4 border-t border-ink-900/10 overflow-hidden">
        {/* Warm bloom behind the globe */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle, rgba(255,158,100,0.10) 0%, transparent 65%)" }}
        />
        <div className="max-w-3xl mx-auto text-center relative z-10">
          <motion.div initial="hidden" whileInView="show" viewport={viewportOnce} variants={fadeUp} className="mb-4">
            <SectionHeader eyebrow="Anywhere On Earth" />
            <h2 className="font-display text-3xl md:text-5xl font-medium text-ink-900 mb-3">
              Spin the globe. <span className="italic text-sunset">Pick a spot.</span>
            </h2>
            <p className="text-ink-400 max-w-md mx-auto">
              Drag to rotate — every marker is a trip TravelOS can plan for you, start to finish.
            </p>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.92 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={viewportOnce}
          transition={{ duration: 0.7, ease: EASE }}
          className="relative z-10 -mt-2"
        >
          <Globe markers={GLOBE_MARKERS} size={460} className="max-w-full" />
        </motion.div>
      </section>

      {/* ════════════════ FEATURE HIGHLIGHTS ════════════════ */}
      <section className="relative py-28 px-4 border-t border-ink-900/10">
        <div className="max-w-6xl mx-auto">
          <motion.div initial="hidden" whileInView="show" viewport={viewportOnce} variants={fadeUp} className="mb-14 text-center">
            <SectionHeader eyebrow="What Makes It Different" />
            <h2 className="font-display text-4xl md:text-5xl font-medium text-ink-900">Intelligence built around you.</h2>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={viewportOnce}
            variants={stagger(0.08)}
            className="grid grid-cols-1 md:grid-cols-3 gap-6"
          >
            {FEATURES.map((f) => (
              <motion.div key={f.title} variants={fadeUp}>
                <TiltCard intensity={4} glow>
                  <div className="glass rounded-xl p-6 h-full hover:shadow-glow transition-shadow duration-300">
                    <div className="w-10 h-10 rounded-lg bg-sunset flex items-center justify-center mb-4">
                      <f.icon className="w-5 h-5 text-[#1F1206]" />
                    </div>
                    <h3 className="font-display text-lg font-medium text-ink-900 mb-2">{f.title}</h3>
                    <p className="text-ink-400 leading-relaxed text-sm">{f.desc}</p>
                  </div>
                </TiltCard>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ════════════════ CTA ════════════════ */}
      <section className="relative py-32 px-4 border-t border-ink-900/10 text-center overflow-hidden">
        {/* Warm ember bloom */}
        <div
          className="absolute left-1/2 bottom-0 -translate-x-1/2 w-[900px] h-[500px] pointer-events-none"
          style={{ background: "radial-gradient(60% 80% at 50% 100%, rgba(255,125,80,0.16) 0%, transparent 70%)" }}
        />
        <motion.div initial="hidden" whileInView="show" viewport={viewportOnce} variants={fadeUp} className="relative z-10">
          <RouteDash from="HERE" to="ANYWHERE" className="max-w-[220px] mx-auto mb-8" />
          <h2 className="font-display text-4xl md:text-6xl font-medium text-ink-900 mb-10 leading-tight">
            Ready to plan your
            <br />
            <span className="italic text-sunset">next trip?</span>
          </h2>
          <Link href="/login">
            <Button size="lg" iconRight={ArrowRight} className="mx-auto">
              Get Started Free
            </Button>
          </Link>
        </motion.div>
      </section>

      {/* ════════════════ FOOTER ════════════════ */}
      <footer className="relative border-t border-ink-900/10 py-12 px-4">
        <div className="max-w-5xl mx-auto flex flex-col items-center gap-6 text-center">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-sunset flex items-center justify-center">
              <Compass className="w-4 h-4 text-[#1F1206]" />
            </div>
            <span className="font-display font-medium text-lg text-ink-900 tracking-wide">TravelOS</span>
          </div>

          <p className="text-xs font-mono text-ink-400">Built with LangGraph · FastAPI · Next.js 14</p>

          <p className="text-xs text-ink-400 max-w-sm leading-relaxed">
            Not affiliated with any booking platform. All recommendations are AI-generated and grounded in real-time API data.
          </p>

          <div className="flex items-center gap-6">
            <Link href="/login" className="text-xs text-ink-400 hover:text-accent transition-colors">
              Sign In
            </Link>
            <span className="text-ink-200">·</span>
            <Link href="/trips" className="text-xs text-ink-400 hover:text-accent transition-colors">
              My Trips
            </Link>
            <span className="text-ink-200">·</span>
            <Link href="/profile" className="text-xs text-ink-400 hover:text-accent transition-colors">
              Profile
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
