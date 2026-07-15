"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Sparkles, CheckCircle2, Loader2 } from "lucide-react";
import { genStartKey } from "@/lib/constants";

// Cumulative elapsed-second thresholds at which each step becomes "active".
// Derived from real worker timing: total ~85 s, itinerary planner is the long pole.
const PIPELINE_STEPS: { label: string; hint: string; startsAt: number }[] = [
  { label: "Travel Style", hint: "Reading your preferences…", startsAt: 0 },
  { label: "Itinerary Planner", hint: "Fetching attractions & weather…", startsAt: 8 },
  { label: "Hotels", hint: "Searching available hotels…", startsAt: 46 },
  { label: "Budget", hint: "Optimising costs…", startsAt: 56 },
  { label: "Events", hint: "Finding local events…", startsAt: 63 },
  { label: "Packing List", hint: "Preparing your packing list…", startsAt: 69 },
  { label: "Validation", hint: "Reviewing the plan…", startsAt: 74 },
  { label: "Saving", hint: "Almost there…", startsAt: 79 },
];

export function AgentProgress({ tripId }: { tripId: string }) {
  const [elapsed, setElapsed] = useState<number>(() => {
    const raw = sessionStorage.getItem(genStartKey(tripId));
    return raw ? Math.floor((Date.now() - Number(raw)) / 1000) : 0;
  });

  useEffect(() => {
    const id = setInterval(() => {
      const raw = sessionStorage.getItem(genStartKey(tripId));
      const start = raw ? Number(raw) : Date.now();
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [tripId]);

  // activeStep = last step whose startsAt threshold has been passed
  const activeStep = PIPELINE_STEPS.reduce((acc, step, i) => (elapsed >= step.startsAt ? i : acc), 0);
  const currentHint = PIPELINE_STEPS[activeStep].hint;

  return (
    <div className="bg-surface border border-ink-900/10 rounded-xl p-8 text-center">
      {/* Animated orb */}
      <motion.div
        animate={{ scale: [1, 1.05, 1] }}
        transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
        className="inline-flex w-20 h-20 mb-8 rounded-full bg-sunset items-center justify-center shadow-glow"
      >
        <Sparkles className="w-8 h-8 text-[#1F1206]" />
      </motion.div>

      <h2 className="font-display text-xl font-medium text-ink-900 mb-1">Building Your Journey</h2>
      <p className="text-sm text-ink-400 mb-2">AI agents are crafting a personalised itinerary. This usually takes 60–90 s.</p>
      <p className="text-xs text-accent mb-10 h-4 transition-all duration-500">{currentHint}</p>

      {/* Pipeline steps */}
      <div className="flex items-center justify-center gap-0 mb-10 flex-wrap gap-y-4">
        {PIPELINE_STEPS.map((step, i) => {
          const done = i < activeStep;
          const active = i === activeStep;
          return (
            <div key={step.label} className="flex items-center">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all duration-500 ${
                    done
                      ? "bg-success-tint border-success text-success"
                      : active
                        ? "bg-accent-tint border-accent text-accent"
                        : "bg-ink-100 border-ink-900/10 text-ink-300"
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : active ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <div className="w-1.5 h-1.5 rounded-full bg-current" />
                  )}
                </div>
                <span
                  className={`text-[10px] font-medium whitespace-nowrap ${done ? "text-success" : active ? "text-accent" : "text-ink-300"}`}
                >
                  {step.label}
                </span>
              </div>

              {i < PIPELINE_STEPS.length - 1 && (
                <div className={`w-8 h-px mx-1 mb-5 transition-all duration-700 ${done ? "bg-success/50" : "bg-ink-900/10"}`} />
              )}
            </div>
          );
        })}
      </div>

      <p className="font-mono text-[10px] text-ink-300 tabular-nums">{elapsed}s elapsed</p>
    </div>
  );
}
