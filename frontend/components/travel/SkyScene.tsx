"use client";

import { motion } from "framer-motion";

/**
 * SkyScene — the Golden Hour hero backdrop that replaces the galaxy StarField.
 * A layered dawn sky with a glowing sun, drifting clouds, a looping plane on a
 * dotted arc, and a paper-cut horizon of mountains + ocean. Pure CSS/SVG, so it
 * drops into any page (landing, login) as an absolute-positioned background.
 */

function Cloud({ className = "", scale = 1 }: { className?: string; scale?: number }) {
  return (
    <div className={className} style={{ transform: `scale(${scale})` }}>
      <svg width="160" height="64" viewBox="0 0 160 64" fill="none" aria-hidden>
        <g fill="#ffffff">
          <ellipse cx="48" cy="42" rx="40" ry="22" />
          <ellipse cx="86" cy="34" rx="34" ry="26" />
          <ellipse cx="118" cy="44" rx="32" ry="20" />
          <rect x="30" y="44" width="104" height="18" rx="9" />
        </g>
      </svg>
    </div>
  );
}

export default function SkyScene({
  showHorizon = true,
  showPlane = true,
  className = "",
}: {
  showHorizon?: boolean;
  showPlane?: boolean;
  className?: string;
}) {
  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}>
      {/* Dawn sky gradient */}
      <div className="absolute inset-0 bg-dawn-gradient" />

      {/* Sun glow */}
      <div className="absolute top-[14%] left-1/2 -translate-x-1/2">
        <div className="w-72 h-72 rounded-full bg-[radial-gradient(circle,rgba(255,200,120,0.9)_0%,rgba(255,170,90,0.45)_40%,transparent_70%)] blur-[6px] animate-sun-pulse" />
      </div>
      <div className="absolute top-[16%] left-1/2 -translate-x-1/2 w-28 h-28 rounded-full bg-[radial-gradient(circle,#fff4dc_0%,#ffd089_70%,transparent_100%)] opacity-90" />

      {/* Drifting clouds */}
      <div className="absolute top-[12%] left-0 w-full animate-cloud-drift opacity-90">
        <Cloud scale={1.1} />
      </div>
      <div className="absolute top-[26%] left-0 w-full animate-cloud-drift-slow opacity-70" style={{ animationDelay: "-30s" }}>
        <Cloud scale={0.75} className="ml-[40%]" />
      </div>
      <div className="absolute top-[40%] left-0 w-full animate-cloud-drift opacity-60" style={{ animationDelay: "-12s", animationDuration: "75s" }}>
        <Cloud scale={0.55} className="ml-[68%]" />
      </div>

      {/* Looping plane on a dotted arc */}
      {showPlane && (
        <div className="absolute inset-0 hidden sm:block">
          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1440 800" preserveAspectRatio="xMidYMid slice" aria-hidden>
            <path
              id="sky-arc"
              d="M -100 380 Q 480 140 760 260 T 1560 220"
              fill="none"
              stroke="rgba(54,163,224,0.35)"
              strokeWidth="2"
              strokeDasharray="2 12"
              strokeLinecap="round"
            />
          </svg>
          <motion.div
            className="absolute top-0 left-0"
            initial={{ offsetDistance: "0%" }}
            animate={{ offsetDistance: "100%" }}
            transition={{ duration: 26, repeat: Infinity, ease: "linear" }}
            style={{
              offsetPath: 'path("M -100 380 Q 480 140 760 260 T 1560 220")',
              offsetRotate: "auto",
            }}
          >
            <svg width="34" height="34" viewBox="0 0 24 24" className="-translate-x-1/2 -translate-y-1/2 drop-shadow-[0_4px_8px_rgba(20,34,61,0.2)]" fill="#ff6b5c" aria-hidden>
              <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0 0 11.5 2 1.5 1.5 0 0 0 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z" />
            </svg>
          </motion.div>
        </div>
      )}

      {/* Paper-cut horizon: mountains + ocean */}
      {showHorizon && (
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 340" className="w-full h-auto" preserveAspectRatio="none" aria-hidden>
            {/* haze layer */}
            <path d="M0 220 L180 170 L340 215 L520 150 L700 205 L880 140 L1080 200 L1280 160 L1440 205 L1440 340 L0 340 Z" fill="#bfe0f4" opacity="0.55" />
            {/* mid range */}
            <path d="M0 260 L160 200 L320 255 L500 190 L680 250 L860 195 L1040 250 L1240 205 L1440 250 L1440 340 L0 340 Z" fill="#86c0b6" opacity="0.85" />
            {/* front range with snow caps */}
            <path d="M0 300 L150 235 L260 280 L420 215 L560 285 L720 230 L900 290 L1080 240 L1280 295 L1440 250 L1440 340 L0 340 Z" fill="#3f7d76" />
            <path d="M420 215 L452 240 L420 248 L392 240 Z" fill="#f4fbfa" opacity="0.9" />
            <path d="M720 230 L748 252 L720 258 L694 252 Z" fill="#f4fbfa" opacity="0.85" />
            <path d="M1080 240 L1106 260 L1080 266 L1056 260 Z" fill="#f4fbfa" opacity="0.85" />
            {/* ocean / sand strip */}
            <rect x="0" y="312" width="1440" height="28" fill="#2f6f6a" />
          </svg>
        </div>
      )}

      {/* fade into page background */}
      <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-b from-transparent to-space-900" />
    </div>
  );
}
