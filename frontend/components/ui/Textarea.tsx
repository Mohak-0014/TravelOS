import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/ui";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({ error = false, className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        "w-full rounded-lg border bg-surface px-3.5 py-2.5 text-sm text-ink-900 outline-none transition-colors duration-150",
        "placeholder:text-ink-300",
        error ? "border-danger" : "border-ink-900/10 focus:border-accent",
        className,
      )}
      {...props}
    />
  );
});
