"use client";

import { useId } from "react";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { springPill } from "@/lib/motion";
import { cn } from "@/lib/ui";

export interface TabItem {
  id: string;
  label: string;
  icon?: LucideIcon;
}

export interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
  variant?: "pill" | "underline";
  className?: string;
}

export function Tabs({ tabs, active, onChange, variant = "pill", className }: TabsProps) {
  // Unique per mount so multiple Tabs instances never share a layoutId.
  const layoutId = useId();

  if (variant === "underline") {
    return (
      <div className={cn("flex items-center gap-1 border-b border-ink-900/10", className)}>
        {tabs.map((tab) => {
          const isActive = tab.id === active;
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={cn(
                "relative flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors duration-150",
                isActive ? "text-ink-900" : "text-ink-400 hover:text-ink-600",
              )}
            >
              {tab.icon && <tab.icon className="w-3.5 h-3.5" />}
              {tab.label}
              {isActive && (
                <motion.div
                  layoutId={`${layoutId}-underline`}
                  className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent"
                  transition={springPill}
                />
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className={cn("inline-flex items-center gap-1 p-1 bg-ink-100 rounded-lg", className)}>
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              "relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-150",
              isActive ? "text-ink-900" : "text-ink-400 hover:text-ink-600",
            )}
          >
            {isActive && (
              <motion.div
                layoutId={`${layoutId}-pill`}
                className="absolute inset-0 bg-surface-raised border border-ink-900/10 rounded-md"
                transition={springPill}
              />
            )}
            {tab.icon && <tab.icon className="relative z-10 w-3.5 h-3.5" />}
            <span className="relative z-10">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}
