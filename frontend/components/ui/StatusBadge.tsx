import { Loader2 } from "lucide-react";
import { STATUS_CONFIG } from "@/lib/constants";
import { Badge } from "./Badge";

export interface StatusBadgeProps {
  status: string;
  spin?: boolean;
  className?: string;
}

export function StatusBadge({ status, spin, className }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.planning;
  const isSpinning = spin ?? status === "generating";
  const Icon = isSpinning ? Loader2 : cfg.icon;

  return (
    <Badge tone={cfg.tone} className={className}>
      <Icon className={`w-3 h-3 ${isSpinning ? "animate-spin" : ""}`} />
      {cfg.label}
    </Badge>
  );
}
