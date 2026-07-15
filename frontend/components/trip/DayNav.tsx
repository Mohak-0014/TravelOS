"use client";

import { motion } from "framer-motion";
import { springPill } from "@/lib/motion";

export function DayNav({ days, activeDay, onSelect }: { days: number[]; activeDay: number; onSelect: (d: number) => void }) {
  return (
    <nav className="flex flex-col gap-0.5">
      <p className="font-mono text-[10px] font-medium text-ink-400 uppercase tracking-wider mb-2 px-2">Days</p>
      {days.map((d) => (
        <button
          key={d}
          onClick={() => onSelect(d)}
          className={`relative w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 ${
            d === activeDay ? "text-accent" : "text-ink-400 hover:text-ink-900"
          }`}
        >
          {d === activeDay && (
            <motion.div layoutId="day-active-bg" className="absolute inset-0 bg-accent-tint rounded-lg" transition={springPill} />
          )}
          <span className="relative z-10">Day {d}</span>
        </button>
      ))}
    </nav>
  );
}
