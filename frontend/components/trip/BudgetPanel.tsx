import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { BudgetDonut, type DonutSlice } from "./BudgetDonut";

export function BudgetPanel({
  slices,
  currency,
  deviationPct,
  budgetTotal,
  stateTotal,
  missingCategories = [],
}: {
  slices: DonutSlice[];
  currency: string;
  deviationPct: number | null;
  budgetTotal: number | null;
  stateTotal: number | null;
  missingCategories?: string[];
}) {
  const total = slices.reduce((s, d) => s + d.value, 0);
  // With flights/hotel unpriced the total is a partial estimate — a "% vs budget"
  // badge would claim a fake surplus, so show what's missing instead. Being OVER
  // budget on partial data is still genuine (missing prices only push it higher).
  const partial = missingCategories.length > 0 && (deviationPct ?? 0) <= 0;

  return (
    <motion.section id="budget-section" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
      <SectionHeader
        eyebrow="Budget Breakdown"
        action={
          partial ? (
            <Badge tone="info">Partial — no {missingCategories.join(" or ")} price</Badge>
          ) : (
            deviationPct != null && (
              <Badge tone={Math.abs(deviationPct) < 5 ? "success" : deviationPct > 0 ? "danger" : "warning"}>
                {deviationPct > 0 ? "+" : ""}
                {deviationPct.toFixed(1)}% vs budget
              </Badge>
            )
          )
        }
      />
      <Card className="space-y-6">
        <BudgetDonut slices={slices} currency={currency} />

        {/* Category bar chart */}
        <div className="space-y-3 pt-4 border-t border-ink-900/10">
          {slices.map((slice) => {
            const pct = total > 0 ? (slice.value / total) * 100 : 0;
            return (
              <div key={slice.label}>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="text-ink-400 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: slice.color }} />
                    {slice.label}
                  </span>
                  <span className="font-mono text-ink-900 font-medium tabular-nums">
                    {currency} {slice.value.toLocaleString()}
                    <span className="text-ink-300 ml-1.5">({pct.toFixed(0)}%)</span>
                  </span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden bg-ink-100">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: slice.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.6, delay: 0.1 }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Total vs budget progress */}
        {budgetTotal != null && stateTotal != null && (
          <div className="pt-4 border-t border-ink-900/10">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-ink-400">Estimated spend vs. budget</span>
              <span className={`font-mono font-medium tabular-nums ${(deviationPct ?? 0) > 0 ? "text-danger" : "text-success"}`}>
                {currency} {stateTotal.toLocaleString()} / {budgetTotal.toLocaleString()}
              </span>
            </div>
            <div className="relative h-2 rounded-full overflow-hidden bg-ink-100">
              <motion.div
                className={`h-full rounded-full ${(deviationPct ?? 0) > 0 ? "bg-danger" : "bg-success"}`}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(100, (stateTotal / budgetTotal) * 100)}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
            </div>
            <p className="text-[10px] text-ink-300 mt-1.5">
              {(deviationPct ?? 0) > 0
                ? `${currency} ${Math.abs(budgetTotal - stateTotal).toLocaleString()} over budget`
                : partial
                  ? `Partial estimate — ${missingCategories.join(" and ")} not priced yet`
                  : `${currency} ${Math.abs(budgetTotal - stateTotal).toLocaleString()} remaining`}
            </p>
          </div>
        )}
      </Card>
    </motion.section>
  );
}
