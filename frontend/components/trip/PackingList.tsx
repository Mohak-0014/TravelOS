"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, CheckCircle2, Luggage, FileText, Shirt, Plug, Pill, Backpack, MapPin, Package, type LucideIcon } from "lucide-react";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Card } from "@/components/ui/Card";
import { EASE } from "@/lib/motion";

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  "Documents & Money": FileText,
  Clothing: Shirt,
  Electronics: Plug,
  "Health & Toiletries": Pill,
  Accessories: Backpack,
  "Destination-Specific": MapPin,
};

export function PackingList({
  packingList,
}: {
  packingList: { categories: Record<string, string[]>; destination_specific?: string[] } | null;
}) {
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());

  if (!packingList || Object.keys(packingList.categories ?? {}).length === 0) return null;

  const allItems = Object.values(packingList.categories).flat();
  const totalItems = allItems.length;
  const checkedCount = checked.size;

  const toggle = (item: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(item)) next.delete(item);
      else next.add(item);
      return next;
    });
  };

  return (
    <motion.section
      id="packing-section"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
    >
      <SectionHeader
        eyebrow="Packing List"
        action={
          <span className="text-xs font-mono text-ink-400">
            {checkedCount}/{totalItems} packed
          </span>
        }
      />
      <ProgressBar value={totalItems > 0 ? (checkedCount / totalItems) * 100 : 0} tone="success" className="mb-4" />

      <Card padding="none" className="overflow-hidden">
        <button
          onClick={() => setOpen((v) => !v)}
          className="w-full flex items-center justify-between px-5 py-4 hover:bg-ink-900/[0.02] transition-colors"
        >
          <span className="text-sm text-ink-400 flex items-center gap-2">
            <Luggage className="w-3.5 h-3.5" />
            {open ? "Hide checklist" : `Show ${totalItems} items across ${Object.keys(packingList.categories).length} categories`}
          </span>
          <ChevronDown className={`w-4 h-4 text-ink-400 transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              key="packing-body"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: EASE }}
              className="overflow-hidden"
            >
              <div className="px-5 pb-5 space-y-5 border-t border-ink-900/10">
                {Object.entries(packingList.categories).map(([cat, items]) => {
                  const Icon = CATEGORY_ICONS[cat] ?? Package;
                  return (
                    <div key={cat} className="pt-4">
                      <div className="flex items-center gap-2 mb-2.5">
                        <Icon className="w-4 h-4 text-ink-400" />
                        <p className="font-mono text-xs font-medium text-ink-400 uppercase tracking-wider">{cat}</p>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                        {items.map((item) => (
                          <button
                            key={item}
                            onClick={() => toggle(item)}
                            className={`flex items-center gap-2.5 text-left px-3 py-2 rounded-lg transition-colors text-xs ${
                              checked.has(item) ? "bg-success-tint text-success" : "bg-ink-100 text-ink-600 hover:bg-ink-100/70"
                            }`}
                          >
                            <div
                              className={`w-4 h-4 rounded-md border shrink-0 flex items-center justify-center transition-colors ${
                                checked.has(item) ? "bg-success border-success" : "border-ink-900/15"
                              }`}
                            >
                              {checked.has(item) && <CheckCircle2 className="w-2.5 h-2.5 text-[#0B1F15]" />}
                            </div>
                            <span className={checked.has(item) ? "line-through opacity-60" : ""}>{item}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.section>
  );
}
