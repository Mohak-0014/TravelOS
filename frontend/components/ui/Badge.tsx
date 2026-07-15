import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/ui";

type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-ink-100 text-ink-600",
  accent: "bg-accent-tint text-accent",
  success: "bg-success-tint text-success",
  warning: "bg-warning-tint text-warning",
  danger: "bg-danger-tint text-danger",
  info: "bg-info-tint text-info",
};

export interface BadgeProps {
  tone?: Tone;
  icon?: LucideIcon;
  className?: string;
  children?: React.ReactNode;
}

export function Badge({ tone = "neutral", icon: Icon, className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full",
        "font-mono text-[10px] font-medium uppercase tracking-wider",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {Icon && <Icon className="w-3 h-3" />}
      {children}
    </span>
  );
}
