"use client";

import { useRef } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { motion, useScroll, useTransform } from "framer-motion";
import { Plane, ArrowRight, ArrowDown, Star, Globe2 } from "lucide-react";
import DaySky from "@/components/travel/DaySky";
import AirplaneBanner from "@/components/travel/AirplaneBanner";
import DestinationShowcase, { DESTINATIONS } from "@/components/travel/DestinationsScroll";

// 3D globe touches WebGL/window — load client-only.
const WorldGlobe = dynamic(() => import("@/components/travel/WorldGlobe"), {
  ssr: false,
  loading: () => (
    <div className="flex aspect-square w-full max-w-[560px] items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-electric-500/30 border-t-electric-400" />
    </div>
  ),
});

// ── Agent pipeline data ───────────────────────────────────────────────────────

const AGENTS = [
  { emoji: "🧭", name: "Travel Style", desc: "Learns your pace, taste, and style", color: "from-electric-400 to-electric-600", glow: "rgba(45,212,191,0.3)" },
  { emoji: "🗺️", name: "Itinerary", desc: "Clusters attractions into walkable zones", color: "from-gold-400 to-gold-500", glow: "rgba(251,191,36,0.3)" },
  { emoji: "🏨", name: "Hotel Agent", desc: "Ranks hotels by your luxury tier + budget", color: "from-coral-400 to-coral-500", glow: "rgba(249,115,22,0.3)" },
  { emoji: "💸", name: "Budget", desc: "Catches overspend. Suggests upgrades.", color: "from-emerald-400 to-emerald-500", glow: "rgba(52,211,153,0.3)" },
  { emoji: "🎭", name: "Local Events", desc: "Finds what's on during your trip", color: "from-purple-400 to-purple-600", glow: "rgba(167,139,250,0.3)" },
  { emoji: "🌤️", name: "Weather", desc: "Replans around rain before you notice", color: "from-electric-400 to-electric-500", glow: "rgba(45,212,191,0.3)" },
  { emoji: "✅", name: "Approval Gate", desc: "You review, you decide — AI proposes, not imposes", color: "from-emerald-400 to-electric-400", glow: "rgba(52,211,153,0.3)" },
  { emoji: "🧳", name: "Memory", desc: "Every trip makes the next one better", color: "from-gold-400 to-coral-400", glow: "rgba(251,191,36,0.3)" },
];

// ── Feature highlights ────────────────────────────────────────────────────────

const FEATURES = [
  { icon: "🎯", title: "Personalization", desc: "Remembers you love rooftop bars. Knows you hate museums before noon. Gets sharper with every trip.", color: "from-electric-400 to-electric-600", border: "hover:border-electric-500/40", glow: "hover:shadow-[0_24px_50px_rgba(14,165,233,0.18)]" },
  { icon: "⚡", title: "Live Adaptation", desc: "Rain forecast on Day 3? We've already moved the outdoor activity indoors. No notification needed.", color: "from-gold-400 to-gold-500", border: "hover:border-gold-400/40", glow: "hover:shadow-[0_24px_50px_rgba(251,191,36,0.18)]" },
  { icon: "💡", title: "Budget Intelligence", desc: "Over by 22%? Here's what to swap. Under by 30%? Here's an upgrade that fits perfectly.", color: "from-coral-400 to-coral-500", border: "hover:border-coral-500/40", glow: "hover:shadow-[0_24px_50px_rgba(244,63,94,0.18)]" },
];

// ── Tokyo demo data ───────────────────────────────────────────────────────────

const DEMO_DAYS = [
  { day: 1, title: "Shibuya", icon: "🏙️", desc: "Crossing & street food", color: "from-electric-400 to-electric-600" },
  { day: 2, title: "Harajuku", icon: "🎌", desc: "Takeshita St & Meiji", color: "from-purple-400 to-gold-400" },
  { day: 3, title: "Asakusa", icon: "⛩️", desc: "Senso-ji & craft market", color: "from-gold-400 to-coral-500" },
];

// ── Scroll-linked flight path (plane flies across the agent pipeline) ──────────

function AnimatedFlightLine() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const dist = useTransform(scrollYProgress, [0.15, 0.85], ["0%", "100%"]);
  const dash = useTransform(scrollYProgress, [0.15, 0.85], [0, 1]);

  return (
    <div ref={ref} className="hidden lg:block absolute top-9 left-0 right-0 pointer-events-none" style={{ zIndex: 0 }}>
      <div className="relative mx-16 route-dash h-0.5" />
      <motion.div
        className="absolute left-16 right-16 top-0 h-0.5 origin-left rounded-full"
        style={{ scaleX: dash, background: "linear-gradient(90deg,#2dd4bf,#7c3aed,#fbbf24)" }}
      />
      <motion.div className="absolute top-0" style={{ left: dist }}>
        <Plane className="w-6 h-6 text-gold-400 -translate-x-1/2 -translate-y-1/2 rotate-90 drop-shadow-[0_4px_8px_rgba(0,0,0,0.4)]" fill="#fbbf24" />
      </motion.div>
    </div>
  );
}

// ── Budget ring ───────────────────────────────────────────────────────────────

function BudgetRing() {
  const size = 100;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - 0.73);

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={50} cy={50} r={r} fill="none" stroke="rgba(231,238,255,0.1)" strokeWidth={stroke} />
        <circle cx={50} cy={50} r={r} fill="none" stroke="url(#budgetGrad)" strokeWidth={stroke} strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" />
        <defs>
          <linearGradient id="budgetGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#2dd4bf" />
            <stop offset="100%" stopColor="#fbbf24" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-sm font-bold text-gold-400">73%</span>
        <span className="text-[9px] text-slate-500 leading-tight">used</span>
      </div>
    </div>
  );
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress: heroScroll } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const skyY = useTransform(heroScroll, [0, 1], [0, 140]);
  const contentY = useTransform(heroScroll, [0, 1], [0, 60]);
  const heroFade = useTransform(heroScroll, [0, 0.7], [1, 0]);

  return (
    <div className="relative bg-space-900 overflow-x-clip">

      {/* ════════════════ SECTION 1 — HERO ════════════════ */}
      <section ref={heroRef} className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden">
        <motion.div style={{ y: skyY }} className="absolute inset-0">
          <DaySky />
        </motion.div>

        {/* the title plane towing its banner */}
        <AirplaneBanner />

        {/* Overlay text */}
        <motion.div style={{ y: contentY, opacity: heroFade }} className="relative z-10 text-center px-4 max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="mb-6"
          >
            <span className="inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-full glass electric-border text-electric-600 uppercase tracking-widest">
              <span className="w-1.5 h-1.5 rounded-full bg-gold-400 animate-pulse-glow" />
              AI-Powered · Always Learning
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-5xl md:text-7xl font-medium leading-[1.04] tracking-tight mb-6"
          >
            <span className="text-slate-100">Where to </span>
            <span className="gradient-text italic">next?</span>
            <br />
            <span className="text-slate-100">We&apos;ll handle the rest.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.22, duration: 0.5 }}
            className="text-lg md:text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed"
          >
            Tell us where. Eight AI agents plan every detail —{" "}
            <span className="text-slate-200 font-medium">and get smarter every trip.</span>
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.32, duration: 0.5 }}
            className="flex items-center justify-center gap-4 flex-wrap"
          >
            <Link href="/login">
              <motion.button whileHover={{ scale: 1.04, y: -2 }} whileTap={{ scale: 0.97 }} className="btn-primary flex items-center gap-2 text-base px-7 py-3.5">
                Start Planning
                <ArrowRight className="w-5 h-5" />
              </motion.button>
            </Link>

            <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={() => scrollToSection("destinations")} className="btn-ghost flex items-center gap-2 text-sm px-6 py-3.5">
              Find your inspiration
              <ArrowDown className="w-4 h-4" />
            </motion.button>
          </motion.div>
        </motion.div>

        {/* Scroll hint */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.2 }} className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 z-10">
          <div className="w-px h-8 bg-gradient-to-b from-transparent to-gold-400/60 animate-float-slow" />
          <div className="w-1.5 h-1.5 rounded-full bg-gold-400/60" />
        </motion.div>
      </section>

      {/* ════════════════ SECTION 2 — DESTINATION SHOWCASE (horizontal scroll) ════════════════ */}
      <DestinationShowcase />

      {/* ════════════════ SECTION 3 — INTERACTIVE GLOBE ════════════════ */}
      <section className="relative py-24 px-4 overflow-hidden bg-space-900">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-px bg-gradient-to-r from-transparent via-electric-500/25 to-transparent" />
        </div>

        <div className="max-w-6xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-80px" }} transition={{ duration: 0.55 }} className="text-center mb-10">
            <p className="text-xs font-semibold text-electric-400 uppercase tracking-[0.2em] mb-4 flex items-center justify-center gap-2">
              <Globe2 className="w-3.5 h-3.5" /> Plan Anywhere
            </p>
            <h2 className="font-display text-4xl md:text-5xl font-medium text-slate-100 mb-4">
              Where will you go <span className="gradient-text italic">first?</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              Spin the globe and plan a trip to absolutely anywhere — a world capital, a quiet
              coastline, a town only you have heard of.
            </p>
          </motion.div>

          <motion.div initial={{ opacity: 0, scale: 0.94 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, margin: "-60px" }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
            <WorldGlobe />
          </motion.div>

          <p className="mt-8 mb-3 text-center text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            A few favorites to spark ideas
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2.5">
            {DESTINATIONS.map((d) => (
              <span
                key={d.id}
                className="rounded-full px-3.5 py-1.5 text-xs font-medium"
                style={{ background: `${d.accent}1a`, color: d.accent, border: `1px solid ${d.accent}33` }}
              >
                {d.name}
              </span>
            ))}
            <Link
              href="/login"
              className="rounded-full border border-gold-400/40 bg-gold-400/10 px-3.5 py-1.5 text-xs font-semibold text-gold-300 transition-colors hover:bg-gold-400/20"
            >
              ✦ Anywhere else →
            </Link>
          </div>
        </div>
      </section>

      {/* ════════════════ SECTION 4 — HOW IT WORKS ════════════════ */}
      <section id="how-it-works" className="relative py-28 px-4 overflow-hidden bg-space-800">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-px bg-gradient-to-r from-transparent via-gold-500/25 to-transparent" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-px bg-gradient-to-r from-transparent via-electric-500/20 to-transparent" />
        </div>

        <div className="max-w-7xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-80px" }} transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }} className="text-center mb-16">
            <p className="text-xs font-semibold text-gold-400 uppercase tracking-[0.2em] mb-4">The Itinerary Engine</p>
            <h2 className="font-display text-4xl md:text-5xl font-medium text-slate-100 mb-5">
              8 Agents. <span className="gradient-text italic">One perfect trip.</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              Your trip runs through a pipeline of specialised AI agents, each optimising a different dimension.
            </p>
          </motion.div>

          <div className="relative">
            <AnimatedFlightLine />
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 relative z-10">
              {AGENTS.map((agent, i) => (
                <motion.div
                  key={agent.name}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-40px" }}
                  transition={{ delay: i * 0.07, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                  whileHover={{ y: -6 }}
                  className="glass-card p-4 flex flex-col items-center text-center gap-3 cursor-default"
                >
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${agent.color} flex items-center justify-center text-xl shadow-soft`}>{agent.emoji}</div>
                  <div>
                    <p className="text-[11px] font-bold text-slate-200 leading-tight">{agent.name}</p>
                    <p className="text-[10px] text-slate-500 mt-1 leading-snug">{agent.desc}</p>
                  </div>
                  <div className="mt-auto w-5 h-5 rounded-full bg-space-700 border border-ink-900/10 flex items-center justify-center">
                    <span className="text-[9px] font-bold text-slate-400">{i + 1}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════ SECTION 5 — FEATURE HIGHLIGHTS ════════════════ */}
      <section className="relative py-24 px-4 bg-space-900">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute top-1/2 left-1/4 w-96 h-96 rounded-full bg-purple-600/10 blur-[120px] -translate-y-1/2" />
          <div className="absolute top-1/2 right-1/4 w-96 h-96 rounded-full bg-electric-500/10 blur-[120px] -translate-y-1/2" />
        </div>

        <div className="max-w-6xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-80px" }} transition={{ duration: 0.55 }} className="text-center mb-14">
            <p className="text-xs font-semibold text-gold-400 uppercase tracking-[0.2em] mb-4">What Makes It Different</p>
            <h2 className="font-display text-4xl md:text-5xl font-medium text-slate-100">
              Intelligence built <span className="gradient-text-gold italic">around you.</span>
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 28 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ delay: i * 0.1, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                whileHover={{ y: -4 }}
                className={`glass-card p-7 transition-all duration-300 ${f.border} ${f.glow}`}
              >
                <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${f.color} flex items-center justify-center text-2xl mb-5 shadow-soft`}>{f.icon}</div>
                <h3 className="text-lg font-bold text-slate-100 mb-3">{f.title}</h3>
                <p className="text-slate-400 leading-relaxed text-sm">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════ SECTION 6 — DEMO + CTA ════════════════ */}
      <section className="relative py-28 px-4 overflow-hidden bg-space-800">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full bg-gold-500/6 blur-[160px]" />
        </div>

        <div className="max-w-5xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-80px" }} transition={{ duration: 0.55 }} className="text-center mb-14">
            <p className="text-xs font-semibold text-electric-400 uppercase tracking-[0.2em] mb-4">See It In Action</p>
            <h2 className="font-display text-4xl md:text-5xl font-medium text-slate-100 mb-4">Tokyo · 5 days · ¥250,000</h2>
            <p className="text-slate-400">A sample trip generated in seconds.</p>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 32 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} className="glass-card p-6 md:p-8 mb-12">
            <div className="flex items-start justify-between gap-4 mb-8 flex-wrap">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl">🗾</span>
                  <h3 className="font-display text-2xl font-semibold text-slate-100">Tokyo, Japan</h3>
                  <span className="status-badge text-emerald-400 bg-emerald-400/15 border border-emerald-400/30">Ready</span>
                </div>
                <p className="text-slate-400 text-sm">Mar 15 – Mar 20, 2025 · 2 travelers</p>
              </div>
              <div className="flex items-center gap-4">
                <BudgetRing />
                <div>
                  <p className="text-xs text-slate-500 mb-1">Budget</p>
                  <p className="text-lg font-bold text-slate-100">¥182,400</p>
                  <p className="text-xs text-slate-500">of ¥250,000</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              {DEMO_DAYS.map((d, i) => (
                <motion.div key={d.day} initial={{ opacity: 0, scale: 0.95 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ delay: 0.1 + i * 0.08, duration: 0.4 }} className="glass-light rounded-xl overflow-hidden">
                  <div className={`h-1.5 bg-gradient-to-r ${d.color}`} />
                  <div className="p-4">
                    <p className="text-xs text-slate-500 mb-1 uppercase tracking-widest">Day {d.day}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{d.icon}</span>
                      <div>
                        <p className="text-sm font-bold text-slate-100">{d.title}</p>
                        <p className="text-xs text-slate-500">{d.desc}</p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="glass-light rounded-xl px-5 py-3.5 flex items-center gap-3">
              <span className="text-2xl">🏨</span>
              <div>
                <p className="text-sm font-bold text-slate-100">Park Hyatt Tokyo · 5★</p>
                <p className="text-xs text-slate-500">¥45,000/night · Shinjuku · Breakfast included</p>
              </div>
              <div className="ml-auto flex items-center gap-1">
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star key={s} className="w-3.5 h-3.5 text-gold-400" fill="#fbbf24" />
                ))}
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-40px" }} transition={{ duration: 0.5 }} className="text-center">
            <p className="text-slate-400 mb-6 text-lg">Ready to plan your trip?</p>
            <Link href="/login">
              <motion.button whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.97 }} className="btn-primary text-base px-10 py-4 flex items-center gap-2 mx-auto">
                Get Started Free
                <ArrowRight className="w-5 h-5" />
              </motion.button>
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ════════════════ SECTION 7 — FOOTER ════════════════ */}
      <footer className="relative border-t border-slate-800 py-12 px-4 bg-space-900">
        <div className="max-w-5xl mx-auto flex flex-col items-center gap-6 text-center">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-electric-gradient flex items-center justify-center shadow-electric-sm">
              <Plane className="w-4 h-4 text-[#0b1437]" />
            </div>
            <span className="font-display font-semibold text-lg gradient-text tracking-wide">TravelOS</span>
          </div>

          <p className="text-xs text-slate-500 font-mono">Built with LangGraph · FastAPI · Next.js 14</p>

          <p className="text-xs text-slate-500 max-w-sm leading-relaxed">
            Not affiliated with any booking platform. All recommendations are AI-generated and grounded in real-time API data.
          </p>

          <div className="flex items-center gap-6">
            <Link href="/login" className="text-xs text-slate-500 hover:text-gold-400 transition-colors">Sign In</Link>
            <span className="text-slate-700">·</span>
            <Link href="/trips" className="text-xs text-slate-500 hover:text-gold-400 transition-colors">My Trips</Link>
            <span className="text-slate-700">·</span>
            <Link href="/profile" className="text-xs text-slate-500 hover:text-gold-400 transition-colors">Profile</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
