import { forwardRef, type ElementType, type HTMLAttributes } from "react";
import { cn } from "@/lib/ui";

const PADDING_CLASSES = {
  none: "",
  sm: "p-4",
  md: "p-6",
} as const;

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: keyof typeof PADDING_CLASSES;
  hover?: boolean;
  /** Frosted-glass treatment — for cards floating over photography. */
  glass?: boolean;
  as?: ElementType;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { padding = "md", hover = false, glass = false, as: Component = "div", className, children, ...props },
  ref,
) {
  return (
    <Component
      ref={ref}
      className={cn(
        glass ? "glass rounded-xl" : "bg-surface border border-ink-900/10 rounded-xl",
        hover && "transition-all duration-200 hover:shadow-lift hover:border-ink-900/20",
        PADDING_CLASSES[padding],
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
});
