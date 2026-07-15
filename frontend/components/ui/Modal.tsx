"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { DUR, EASE } from "@/lib/motion";
import { cn } from "@/lib/ui";

const WIDTH_CLASSES = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
} as const;

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  footer?: React.ReactNode;
  width?: keyof typeof WIDTH_CLASSES;
  children?: React.ReactNode;
}

export function Modal({ open, onClose, title, footer, width = "md", children }: ModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DUR.fast }}
            className="absolute inset-0 bg-black/65 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ duration: DUR.base, ease: EASE }}
            className={cn("relative w-full bg-surface rounded-xl border border-ink-900/10 shadow-overlay", WIDTH_CLASSES[width])}
          >
            {title && (
              <div className="flex items-center justify-between px-6 py-4 border-b border-ink-900/10">
                <h2 className="font-display text-lg font-medium text-ink-900">{title}</h2>
                <button
                  onClick={onClose}
                  className="p-1 rounded-md text-ink-400 hover:text-ink-900 hover:bg-ink-900/5 transition-colors"
                  aria-label="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
            <div className="p-6">{children}</div>
            {footer && <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-ink-900/10">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
