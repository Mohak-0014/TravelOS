import { cn } from "@/lib/ui";

type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-ink-900",
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

export interface StatProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: Tone;
  className?: string;
}

export function Stat({ label, value, hint, tone = "neutral", className }: StatProps) {
  return (
    <div className={className}>
      <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-1">{label}</p>
      <p className={cn("font-mono text-2xl font-medium tabular-nums", TONE_TEXT[tone])}>{value}</p>
      {hint && <p className="text-xs text-ink-400 mt-0.5">{hint}</p>}
    </div>
  );
}
