"use client";

import { forwardRef } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/ui";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  // Sunset gradient with a dark label — the one hot element on every screen.
  // hover:shadow-glow makes it bloom against the midnight ground.
  primary: "bg-sunset text-[#1F1206] shadow-[0_0_0_1px_rgba(255,158,100,0.25)] hover:shadow-glow transition-shadow",
  secondary: "bg-surface-raised text-ink-900 border border-ink-900/10 hover:border-accent/50",
  ghost: "bg-transparent text-ink-600 hover:bg-ink-900/5 hover:text-ink-900",
  danger: "bg-danger text-[#2E0B07] hover:bg-danger-deep",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-lg",
  lg: "h-12 px-6 text-base gap-2 rounded-xl",
};

const ICON_SIZE: Record<Size, string> = {
  sm: "w-3.5 h-3.5",
  md: "w-4 h-4",
  lg: "w-5 h-5",
};

export interface ButtonProps extends Omit<HTMLMotionProps<"button">, "children"> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  iconLeft?: LucideIcon;
  iconRight?: LucideIcon;
  children?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, iconLeft: IconLeft, iconRight: IconRight, disabled, className, children, ...props },
  ref,
) {
  const iconSize = ICON_SIZE[size];
  return (
    <motion.button
      ref={ref}
      whileTap={disabled || loading ? undefined : { y: 1 }}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center font-medium whitespace-nowrap transition-colors duration-150",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className={cn(iconSize, "animate-spin")} /> : IconLeft && <IconLeft className={iconSize} />}
      {children}
      {!loading && IconRight && <IconRight className={iconSize} />}
    </motion.button>
  );
});
