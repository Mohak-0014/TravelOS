"use client";

/**
 * DaySky — the Daylight Voyage hero backdrop.
 * A clear blue daytime sky: soft sky-blue gradient, a warm sun with a gentle
 * glow, fluffy white clouds drifting across, a couple of distant birds, and a
 * light, hazy ridge along the horizon. Pure CSS/SVG so it drops behind any
 * hero as an absolute background. No randomness, so it is SSR-safe.
 */

function Cloud({ className = "", scale = 1 }: { className?: string; scale?: number }) {
  return (
    <div className={className} style={{ transform: `scale(${scale})` }}>
      <svg width="200" height="80" viewBox="0 0 160 64" fill="none" aria-hidden>
        <g fill="rgba(255, 255, 255, 0.92)">
          <ellipse cx="48" cy="42" rx="40" ry="22" />
          <ellipse cx="86" cy="34" rx="34" ry="26" />
          <ellipse cx="118" cy="44" rx="32" ry="20" />
          <rect x="30" y="44" width="104" height="18" rx="9" />
        </g>
        {/* soft underside shadow */}
        <ellipse cx="84" cy="58" rx="60" ry="6" fill="rgba(148,184,226,0.18)" />
      </svg>
    </div>
  );
}

function Bird({ className = "" }: { className?: string }) {
  return (
    <svg width="26" height="12" viewBox="0 0 26 12" className={className} aria-hidden>
      <path
        d="M1 8 Q7 1 13 7 Q19 1 25 8"
        fill="none"
        stroke="rgba(71,85,105,0.55)"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function DaySky({
  showHorizon = true,
  className = "",
}: {
  showHorizon?: boolean;
  className?: string;
}) {
  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}>
      {/* Clear daytime sky gradient */}
      <div className="absolute inset-0 bg-dawn-gradient" />

      {/* Warm sun wash from the upper area */}
      <div className="absolute -top-24 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(255,247,224,0.85)_0%,rgba(251,191,36,0.18)_38%,transparent_70%)]" />

      {/* The sun */}
      <div className="absolute top-[14%] right-[16%]">
        <div className="h-40 w-40 rounded-full bg-[radial-gradient(circle,rgba(255,244,214,0.65)_0%,rgba(251,191,36,0.22)_45%,transparent_72%)] blur-[2px] animate-float-slow" />
        <div className="absolute left-[28px] top-[28px] h-[84px] w-[84px] rounded-full bg-[radial-gradient(circle_at_38%_34%,#fffaf0_0%,#ffe9ad_55%,#fbbf24_100%)] shadow-[0_0_70px_rgba(251,191,36,0.55)]" />
      </div>

      {/* Distant birds */}
      <Bird className="absolute left-[22%] top-[26%] opacity-70 animate-float-medium" />
      <Bird className="absolute left-[28%] top-[31%] scale-75 opacity-50 animate-float-slow" />
      <Bird className="absolute right-[34%] top-[20%] scale-90 opacity-60 animate-float-medium" />

      {/* Drifting clouds */}
      <div className="absolute top-[16%] left-0 w-full animate-cloud-drift-slow opacity-95">
        <Cloud scale={1.15} />
      </div>
      <div
        className="absolute top-[40%] left-0 w-full animate-cloud-drift opacity-85"
        style={{ animationDelay: "-30s", animationDuration: "80s" }}
      >
        <Cloud scale={0.75} className="ml-[55%]" />
      </div>
      <div
        className="absolute top-[58%] left-0 w-full animate-cloud-drift-slow opacity-70"
        style={{ animationDelay: "-50s" }}
      >
        <Cloud scale={0.55} className="ml-[20%]" />
      </div>

      {/* Hazy ridge along the horizon (light, sunlit silhouettes) */}
      {showHorizon && (
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 340" className="h-auto w-full" preserveAspectRatio="none" aria-hidden>
            <path
              d="M0 220 L180 170 L340 215 L520 150 L700 205 L880 140 L1080 200 L1280 160 L1440 205 L1440 340 L0 340 Z"
              fill="#bcd6f2"
              opacity="0.5"
            />
            <path
              d="M0 260 L160 200 L320 255 L500 190 L680 250 L860 195 L1040 250 L1240 205 L1440 250 L1440 340 L0 340 Z"
              fill="#d4e6fa"
              opacity="0.7"
            />
            <path
              d="M0 300 L150 235 L260 280 L420 215 L560 285 L720 230 L900 290 L1080 240 L1280 295 L1440 250 L1440 340 L0 340 Z"
              fill="#e8f2fc"
            />
            {/* warm rim-light on a couple of peaks */}
            <path d="M420 215 L452 240 L420 248 L392 240 Z" fill="#fcd34d" opacity="0.55" />
            <path d="M880 140 L905 162 L880 170 L856 162 Z" fill="#fbbf24" opacity="0.45" />
          </svg>
        </div>
      )}

      {/* fade into page background */}
      <div className="absolute bottom-0 left-0 right-0 h-28 bg-gradient-to-b from-transparent to-space-900" />
    </div>
  );
}
