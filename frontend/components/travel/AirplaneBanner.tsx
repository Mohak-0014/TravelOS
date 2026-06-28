"use client";

import { motion, useReducedMotion } from "framer-motion";

/**
 * AirplaneBanner — the site mascot. A gold-lit plane loops across the sky
 * towing a rippling cloth banner that reads "TravelOS". Built from SVG +
 * framer-motion (no images). Honors prefers-reduced-motion by parking the
 * plane mid-sky without the cross-screen loop or flutter.
 */

function Plane() {
  return (
    <div
      className="shrink-0 drop-shadow-[0_6px_14px_rgba(0,0,0,0.45)]"
      style={{ transform: "rotate(80deg)" }}
    >
      <svg width="50" height="50" viewBox="0 0 24 24" aria-hidden>
        <defs>
          <linearGradient id="planeGold" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#fde68a" />
            <stop offset="55%" stopColor="#fbbf24" />
            <stop offset="100%" stopColor="#f59e0b" />
          </linearGradient>
        </defs>
        <path
          d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0 0 11.5 2 1.5 1.5 0 0 0 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"
          fill="url(#planeGold)"
        />
      </svg>
    </div>
  );
}

function Banner({ wave }: { wave: boolean }) {
  return (
    <motion.div
      animate={wave ? { skewY: [-1.4, 1.4, -1.4], rotateZ: [-0.6, 0.6, -0.6] } : undefined}
      transition={{ duration: 3.6, repeat: Infinity, ease: "easeInOut" }}
      style={{ transformOrigin: "right center" }}
      className="relative"
    >
      <div
        className="relative flex items-center justify-center px-7 py-2.5 shadow-[0_8px_20px_rgba(0,0,0,0.35)]"
        style={{
          background: "linear-gradient(135deg, #fff7e0 0%, #fcd34d 55%, #f59e0b 100%)",
          clipPath: "polygon(0 0, 100% 0, 100% 100%, 0 100%, 12% 50%)",
          minWidth: 188,
        }}
      >
        {/* cloth seams */}
        <span className="absolute inset-y-1 left-[28%] w-px bg-[#0b1437]/10" />
        <span className="absolute inset-y-1 left-[52%] w-px bg-[#0b1437]/10" />
        <span className="absolute inset-y-1 left-[76%] w-px bg-[#0b1437]/10" />
        <span className="font-display font-semibold tracking-wide text-[#0b1437] text-lg md:text-xl pl-3 select-none">
          TravelOS
        </span>
      </div>
      {/* grommets along the top */}
      <span className="absolute -top-0.5 left-[20%] w-1 h-1 rounded-full bg-[#0b1437]/40" />
      <span className="absolute -top-0.5 left-1/2 w-1 h-1 rounded-full bg-[#0b1437]/40" />
      <span className="absolute -top-0.5 left-[80%] w-1 h-1 rounded-full bg-[#0b1437]/40" />
    </motion.div>
  );
}

export default function AirplaneBanner() {
  const reduce = useReducedMotion();

  const Group = (
    <div className="flex items-center">
      <Banner wave={!reduce} />
      {/* tow rope */}
      <div className="w-7 h-px route-dash shrink-0" />
      <Plane />
    </div>
  );

  if (reduce) {
    return (
      <div className="absolute top-[24%] left-1/2 -translate-x-1/2 z-[5] pointer-events-none">
        {Group}
      </div>
    );
  }

  return (
    <div className="absolute top-[22%] left-0 right-0 z-[5] pointer-events-none">
      <motion.div
        className="absolute"
        initial={{ x: "-45vw" }}
        animate={{ x: "118vw" }}
        transition={{ duration: 26, repeat: Infinity, ease: "linear" }}
      >
        <motion.div
          animate={{ y: [0, -10, 0], rotate: [-1.2, 1.2, -1.2] }}
          transition={{ duration: 5.5, repeat: Infinity, ease: "easeInOut" }}
        >
          {Group}
        </motion.div>
      </motion.div>
    </div>
  );
}
