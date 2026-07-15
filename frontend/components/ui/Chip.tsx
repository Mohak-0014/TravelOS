"use client";

import { forwardRef } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/ui";

export interface ChipProps extends Omit<HTMLMotionProps<"button">, "children"> {
  selected?: boolean;
  icon?: LucideIcon;
  children?: React.ReactNode;
}

export const Chip = forwardRef<HTMLButtonElement, ChipProps>(function Chip(
  { selected = false, icon: Icon, className, children, ...props },
  ref,
) {
  return (
    <motion.button
      ref={ref}
      type="button"
      whileTap={{ y: 1 }}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-colors duration-150 text-left",
        selected
          ? "bg-accent-tint border-accent/30 text-accent"
          : "bg-surface border-ink-900/10 text-ink-600 hover:border-ink-900/20 hover:text-ink-900",
        className,
      )}
      {...props}
    >
      {Icon && <Icon className="w-3.5 h-3.5 shrink-0" />}
      {children}
    </motion.button>
  );
});
