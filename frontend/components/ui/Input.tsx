import { forwardRef, type InputHTMLAttributes } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/ui";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: LucideIcon;
  error?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ icon: Icon, error = false, className, ...props }, ref) {
  return (
    <div className="relative">
      {Icon && <Icon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400 pointer-events-none" />}
      <input
        ref={ref}
        className={cn(
          "w-full h-10 rounded-lg border bg-surface px-3.5 text-sm text-ink-900 outline-none transition-colors duration-150",
          "placeholder:text-ink-300",
          error ? "border-danger" : "border-ink-900/10 focus:border-accent",
          Icon && "pl-10",
          className,
        )}
        {...props}
      />
    </div>
  );
});
