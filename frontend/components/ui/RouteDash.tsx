"use client";

import { motion } from "framer-motion";
import { drawPath, viewportOnce } from "@/lib/motion";
import { cn } from "@/lib/ui";

export interface RouteDashProps {
  from?: string;
  to?: string;
  arc?: boolean;
  animate?: boolean;
  className?: string;
}

/** Animated dashed route line — the recurring "flight path" motif. Endpoint dots
 * are plain CSS so they stay crisp regardless of how the SVG between them stretches. */
export function RouteDash({ from, to, arc = false, animate = true, className }: RouteDashProps) {
  const d = arc ? "M0,20 Q 100,-4 200,20" : "M0,10 L200,10";
  return (
    <div className={cn("flex items-center gap-3", className)}>
      {from && <span className="font-mono text-xs tracking-widest text-ink-400 shrink-0">{from}</span>}
      <div className="relative flex-1 min-w-[48px] h-5 flex items-center">
        <span className="absolute left-0 w-1.5 h-1.5 rounded-full bg-accent" />
        <svg viewBox={`0 0 200 ${arc ? 24 : 20}`} className="w-full h-full" preserveAspectRatio="none" fill="none">
          <motion.path
            d={d}
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="3 6"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
            className="text-ink-300"
            initial={animate ? "hidden" : undefined}
            whileInView={animate ? "show" : undefined}
            viewport={viewportOnce}
            variants={drawPath}
          />
        </svg>
        <span className="absolute right-0 w-1.5 h-1.5 rounded-full bg-accent" />
      </div>
      {to && <span className="font-mono text-xs tracking-widest text-ink-400 shrink-0">{to}</span>}
    </div>
  );
}
