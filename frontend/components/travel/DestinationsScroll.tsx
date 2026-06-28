"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  motion,
  useScroll,
  useTransform,
  useMotionValue,
  useSpring,
} from "framer-motion";
import { MapPin, ArrowUpRight, MousePointer2, Globe2 } from "lucide-react";

export interface Destination {
  id: string;
  name: string;
  country: string;
  blurb: string;
  glyph: string;
  from: string;
  to: string;
  accent: string;
}

/**
 * A rotating set of popular travel cities used purely as *inspiration* on the
 * landing page — never presented as the full catalogue. The closing panel and
 * surrounding copy make clear TravelOS plans trips to anywhere on Earth.
 */
export const DESTINATIONS: Destination[] = [
  {
    id: "tokyo",
    name: "Tokyo",
    country: "Japan",
    blurb: "Neon canyons and quiet shrines — the future and the past on one train line.",
    glyph: "🗼",
    from: "#fb7185",
    to: "#f97316",
    accent: "#fff1f2",
  },
  {
    id: "paris",
    name: "Paris",
    country: "France",
    blurb: "Golden-hour rooftops, river light, and a café table with your name on it.",
    glyph: "🗼",
    from: "#60a5fa",
    to: "#6366f1",
    accent: "#eff6ff",
  },
  {
    id: "new-york",
    name: "New York",
    country: "USA",
    blurb: "The city that dares you to keep up — skyline, bagels, and a hundred neighborhoods.",
    glyph: "🌆",
    from: "#38bdf8",
    to: "#0284c7",
    accent: "#f0f9ff",
  },
  {
    id: "bali",
    name: "Bali",
    country: "Indonesia",
    blurb: "Rice terraces stepping down to the sea, temples wrapped in morning mist.",
    glyph: "🏝️",
    from: "#34d399",
    to: "#0d9488",
    accent: "#ecfdf5",
  },
  {
    id: "cape-town",
    name: "Cape Town",
    country: "South Africa",
    blurb: "Where a flat-topped mountain meets two oceans and the light never quits.",
    glyph: "⛰️",
    from: "#fbbf24",
    to: "#ea580c",
    accent: "#fffbeb",
  },
  {
    id: "lisbon",
    name: "Lisbon",
    country: "Portugal",
    blurb: "Tiled façades, rattling trams, and pastel hills tumbling toward the Tagus.",
    glyph: "🚋",
    from: "#fda4af",
    to: "#e11d48",
    accent: "#fff1f2",
  },
  {
    id: "reykjavik",
    name: "Reykjavík",
    country: "Iceland",
    blurb: "A pastel harbour town under wide skies — waterfalls and aurora a short drive away.",
    glyph: "🌋",
    from: "#7dd3fc",
    to: "#6366f1",
    accent: "#f0f9ff",
  },
  {
    id: "marrakech",
    name: "Marrakech",
    country: "Morocco",
    blurb: "A maze of spice, lantern light, and rooftop mint tea above the medina.",
    glyph: "🕌",
    from: "#fb923c",
    to: "#d97706",
    accent: "#fff7ed",
  },
];

// ── A single destination "poster" with optional 3D tilt ─────────────────────

function DestinationCard({ d, tilt }: { d: Destination; tilt: boolean }) {
  const rx = useMotionValue(0);
  const ry = useMotionValue(0);
  const srx = useSpring(rx, { stiffness: 150, damping: 18 });
  const sry = useSpring(ry, { stiffness: 150, damping: 18 });

  function handleMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!tilt) return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    ry.set(px * 14);
    rx.set(-py * 14);
  }
  function reset() {
    rx.set(0);
    ry.set(0);
  }

  return (
    <motion.div
      onMouseMove={handleMove}
      onMouseLeave={reset}
      style={{
        rotateX: tilt ? srx : 0,
        rotateY: tilt ? sry : 0,
        transformPerspective: 1000,
        backgroundImage: `radial-gradient(ellipse at 50% 18%, ${d.accent}40 0%, transparent 55%), linear-gradient(160deg, ${d.from} 0%, ${d.to} 100%)`,
      }}
      className="noise relative h-[68vh] w-full overflow-hidden rounded-[28px] border border-white/30 shadow-[0_24px_60px_rgba(15,23,42,0.18)]"
    >
      {/* glyph */}
      <div
        className="absolute right-4 top-1/2 -translate-y-1/2 select-none text-[15rem] leading-none opacity-90 drop-shadow-[0_12px_40px_rgba(15,23,42,0.25)]"
        aria-hidden
      >
        {d.glyph}
      </div>
      {/* soft glow behind glyph */}
      <div
        className="absolute right-10 top-1/2 h-72 w-72 -translate-y-1/2 rounded-full blur-3xl"
        style={{ background: "#ffffff", opacity: 0.22 }}
      />

      {/* copy */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/40 to-transparent p-8 md:p-10">
        <span className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-semibold tracking-wide text-white ring-1 ring-white/40">
          <MapPin className="h-3 w-3" />
          {d.country}
        </span>
        <h3 className="font-display text-3xl font-medium leading-tight text-white md:text-5xl">
          {d.name}
        </h3>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-white/85 md:text-base">
          {d.blurb}
        </p>
        <Link
          href="/login"
          className="pointer-events-auto mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-white transition-colors hover:text-white/80"
        >
          Plan a trip here
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
    </motion.div>
  );
}

// ── The intro panel that leads the horizontal track ─────────────────────────

function IntroPanel() {
  return (
    <div className="flex h-[68vh] w-full flex-col justify-center pr-8">
      <p className="mb-4 text-xs font-semibold uppercase tracking-[0.25em] text-electric-600">
        Endless inspiration
      </p>
      <h2 className="font-display text-5xl font-medium leading-[1.02] text-slate-100 md:text-7xl">
        Where to <span className="gradient-text italic">begin?</span>
      </h2>
      <p className="mt-6 max-w-sm text-lg leading-relaxed text-slate-400">
        A few of the world&apos;s most-loved cities to spark ideas — but your trip can start
        absolutely anywhere.
      </p>
      <div className="mt-8 flex items-center gap-2 text-sm text-slate-500">
        <MousePointer2 className="h-4 w-4" />
        Scroll to travel →
      </div>
    </div>
  );
}

// ── Closing panel: the whole point — we go anywhere ─────────────────────────

function AnywherePanel() {
  return (
    <div className="glass-card flex h-[68vh] w-full flex-col items-center justify-center p-10 text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-electric-gradient shadow-electric">
        <Globe2 className="h-8 w-8 text-white" />
      </div>
      <h3 className="font-display text-4xl font-medium leading-tight text-slate-100 md:text-5xl">
        …and <span className="gradient-text italic">anywhere</span> else.
      </h3>
      <p className="mt-5 max-w-md text-base leading-relaxed text-slate-400">
        These are just a spark. Name any city on Earth — a megacity or a mountain village — and the
        agents plan the rest around you.
      </p>
      <Link href="/login" className="mt-7">
        <span className="btn-primary inline-flex items-center gap-2 px-7 py-3.5 text-base">
          Plan your trip
          <ArrowUpRight className="h-5 w-5" />
        </span>
      </Link>
    </div>
  );
}

// ── Desktop: pinned vertical-scroll drives horizontal travel ────────────────

function DesktopTrack() {
  const targetRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const [distance, setDistance] = useState(0);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const measure = () => setDistance(Math.max(0, track.scrollWidth - window.innerWidth));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(track);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  const { scrollYProgress } = useScroll({
    target: targetRef,
    offset: ["start start", "end end"],
  });
  const x = useTransform(scrollYProgress, [0, 1], [0, -distance]);
  const progress = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);

  return (
    <section
      ref={targetRef}
      className="relative hidden md:block"
      style={{ height: `calc(100vh + ${distance}px)` }}
      aria-label="Destination inspiration"
    >
      <div className="sticky top-0 flex h-screen items-center overflow-hidden">
        <motion.div
          ref={trackRef}
          style={{ x }}
          className="flex items-center gap-7 pl-[7vw] pr-[7vw] will-change-transform"
        >
          <div className="w-[34vw] shrink-0">
            <IntroPanel />
          </div>
          {DESTINATIONS.map((d) => (
            <div key={d.id} className="w-[46vw] shrink-0">
              <DestinationCard d={d} tilt />
            </div>
          ))}
          <div className="w-[42vw] shrink-0">
            <AnywherePanel />
          </div>
        </motion.div>

        {/* progress bar */}
        <div className="absolute bottom-10 left-1/2 h-1 w-48 -translate-x-1/2 overflow-hidden rounded-full bg-ink-900/10">
          <motion.div className="h-full rounded-full bg-gradient-to-r from-electric-400 to-gold-400" style={{ width: progress }} />
        </div>
      </div>
    </section>
  );
}

// ── Mobile: native horizontal scroll-snap carousel ──────────────────────────

function MobileTrack() {
  return (
    <section className="px-4 py-16 md:hidden" aria-label="Destination inspiration">
      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-electric-600">
        Endless inspiration
      </p>
      <h2 className="mb-2 font-display text-4xl font-medium leading-tight text-slate-100">
        Where to <span className="gradient-text italic">begin?</span>
      </h2>
      <p className="mb-6 max-w-xs text-sm text-slate-400">
        A few favorites to spark ideas — your trip can start anywhere.
      </p>
      <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {DESTINATIONS.map((d) => (
          <div key={d.id} className="w-[82vw] shrink-0 snap-center">
            <DestinationCard d={d} tilt={false} />
          </div>
        ))}
        <div className="w-[82vw] shrink-0 snap-center">
          <AnywherePanel />
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-slate-500">Swipe to explore →</p>
    </section>
  );
}

export default function DestinationShowcase() {
  return (
    <div id="destinations" className="relative bg-space-900">
      <DesktopTrack />
      <MobileTrack />
    </div>
  );
}
