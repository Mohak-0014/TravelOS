import { motion } from "framer-motion";
import { DUR, EASE } from "@/lib/motion";
import { cn } from "@/lib/ui";

type Tone = "accent" | "success" | "warning" | "danger" | "info";

const TONE_FILL: Record<Tone, string> = {
  accent: "bg-sunset",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
};

export interface ProgressBarProps {
  value: number; // 0-100
  tone?: Tone;
  className?: string;
}

export function ProgressBar({ value, tone = "accent", className }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("h-1.5 rounded-full bg-ink-100 overflow-hidden", className)}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={{ duration: DUR.slow, ease: EASE }}
        className={cn("h-full rounded-full", TONE_FILL[tone])}
      />
    </div>
  );
}
