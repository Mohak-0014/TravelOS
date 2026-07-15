"use client";

import { motion, AnimatePresence } from "framer-motion";
import { MapPin, AlertCircle, Compass, X, Loader2 } from "lucide-react";
import type { ItineraryItemOut, WeatherDay } from "@/lib/api";
import { ITEM_ICONS } from "@/lib/constants";
import { convertToBudgetCurrency } from "@/lib/currency";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { WeatherIcon } from "./WeatherStrip";

const TONE_TEXT: Record<string, string> = {
  accent: "text-accent bg-accent-tint",
  warning: "text-warning bg-warning-tint",
  info: "text-info bg-info-tint",
  success: "text-success bg-success-tint",
  danger: "text-danger bg-danger-tint",
  neutral: "text-ink-400 bg-ink-100",
};

function ItineraryItem({
  item,
  isLast,
  budgetCurrency,
  replaceTarget,
  replaceTitle,
  setReplaceTitle,
  replaceLoading,
  onReplaceTargetToggle,
  onReplaceSubmit,
  onReplaceCancel,
}: {
  item: ItineraryItemOut;
  isLast: boolean;
  budgetCurrency: string;
  replaceTarget: string | null;
  replaceTitle: string;
  setReplaceTitle: (v: string) => void;
  replaceLoading: boolean;
  onReplaceTargetToggle: (itemId: string) => void;
  onReplaceSubmit: (itemId: string) => void;
  onReplaceCancel: () => void;
}) {
  const typeInfo = ITEM_ICONS[item.item_type] ?? ITEM_ICONS.activity;
  const ItemIcon = typeInfo.icon;
  const toneCls = TONE_TEXT[typeInfo.tone];
  const isReplacing = replaceTarget === item.id;

  return (
    <motion.div whileHover={{ x: 3 }} transition={{ duration: 0.15 }}>
      <div className="flex gap-4 py-3">
        {/* Timeline line + icon */}
        <div className="flex flex-col items-center shrink-0">
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${toneCls}`}>
            <ItemIcon className="w-3.5 h-3.5" strokeWidth={2} />
          </div>
          {!isLast && <div className="w-px flex-1 bg-ink-900/10 mt-1.5 min-h-[16px]" />}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 pb-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              {item.start_time && <p className="text-[10px] text-ink-300 font-mono mb-0.5">{item.start_time}</p>}
              <p className="text-sm font-medium text-ink-900 leading-snug">{item.title}</p>
              {item.address && (
                <p className="text-xs text-ink-400 truncate mt-0.5 flex items-center gap-1">
                  <MapPin className="w-2.5 h-2.5 shrink-0" />
                  {item.address}
                </p>
              )}
              {item.description && <p className="text-xs text-ink-400 mt-1 line-clamp-2 leading-relaxed">{item.description}</p>}
            </div>

            <div className="flex flex-col items-end gap-1.5 shrink-0">
              {item.est_cost != null &&
                (() => {
                  const cv = convertToBudgetCurrency(item.est_cost, item.est_cost_currency ?? budgetCurrency, budgetCurrency);
                  return (
                    <span className="font-mono text-xs font-medium text-accent tabular-nums whitespace-nowrap">
                      {budgetCurrency} {Math.round(cv).toLocaleString("en-IN")}
                    </span>
                  );
                })()}
              <button
                onClick={() => onReplaceTargetToggle(item.id)}
                className="text-[10px] text-ink-300 hover:text-accent transition-colors px-2 py-0.5 rounded-lg hover:bg-accent-tint"
              >
                Replace
              </button>
            </div>
          </div>

          {/* Replace form */}
          <AnimatePresence>
            {isReplacing && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-2 flex gap-2 items-center overflow-hidden"
              >
                <Input
                  autoFocus
                  type="text"
                  value={replaceTitle}
                  onChange={(e) => setReplaceTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") onReplaceSubmit(item.id);
                    if (e.key === "Escape") onReplaceCancel();
                  }}
                  placeholder="Replacement activity name…"
                  disabled={replaceLoading}
                  className="text-xs h-9 flex-1"
                />
                <Button size="sm" onClick={() => onReplaceSubmit(item.id)} disabled={replaceLoading || !replaceTitle.trim()}>
                  {replaceLoading ? "…" : "Submit"}
                </Button>
                <button onClick={onReplaceCancel} className="text-ink-400 hover:text-ink-900">
                  <X className="w-4 h-4" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Conflict warning */}
          {item.conflict_warning && (
            <div className="mt-2 flex items-start gap-1.5 text-xs text-warning bg-warning-tint rounded-lg px-3 py-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{item.conflict_warning}</span>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function ItinerarySection({
  dayNumbers,
  itemsByDay,
  weatherDays,
  budgetCurrency,
  tripStatus,
  onRegenerate,
  regenerating,
  setDaySectionRef,
  onAskConcierge,
  ...replaceProps
}: {
  dayNumbers: number[];
  itemsByDay: Record<number, ItineraryItemOut[]>;
  weatherDays: WeatherDay[];
  budgetCurrency: string;
  tripStatus: string;
  onRegenerate: () => void;
  regenerating: boolean;
  setDaySectionRef: (day: number) => (el: HTMLElement | null) => void;
  onAskConcierge: (day: number) => void;
  replaceTarget: string | null;
  replaceTitle: string;
  setReplaceTitle: (v: string) => void;
  replaceLoading: boolean;
  onReplaceTargetToggle: (itemId: string) => void;
  onReplaceSubmit: (itemId: string) => void;
  onReplaceCancel: () => void;
}) {
  if (dayNumbers.length === 0) return null;

  return (
    <section>
      <SectionHeader
        eyebrow="Itinerary"
        action={
          tripStatus === "planned" && (
            <button onClick={onRegenerate} disabled={regenerating} className="text-xs text-ink-400 hover:text-accent transition-colors">
              Regenerate
            </button>
          )
        }
      />

      <div className="space-y-4">
        {dayNumbers.map((day, idx) => {
          const dayItems = [...(itemsByDay[day] ?? [])].sort((a, b) => a.sort_order - b.sort_order);
          const dayWeather = weatherDays[day - 1];

          return (
            <motion.div
              key={day}
              ref={setDaySectionRef(day)}
              data-day={day}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ delay: idx * 0.05, duration: 0.4 }}
            >
              <Card padding="none" className="overflow-hidden">
                {/* Day header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-ink-900/10">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-accent-tint flex items-center justify-center">
                      <span className="font-mono text-xs font-medium text-accent">{day}</span>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-ink-900">Day {day}</p>
                      {dayItems[0]?.item_date && (
                        <p className="text-xs text-ink-400">
                          {new Date(dayItems[0].item_date + "T00:00:00").toLocaleDateString("en-US", {
                            weekday: "short",
                            month: "short",
                            day: "numeric",
                          })}
                        </p>
                      )}
                    </div>
                  </div>

                  {dayWeather && (
                    <div className="flex items-center gap-2 text-xs font-mono text-ink-400">
                      <WeatherIcon code={dayWeather.condition_code} adverse={dayWeather.is_adverse} />
                      <span>
                        {Math.round(dayWeather.temp_min_c)}–{Math.round(dayWeather.temp_max_c)}°C
                      </span>
                    </div>
                  )}
                </div>

                {/* Activity timeline */}
                <div className="px-5 py-4 space-y-0">
                  {dayItems.map((item, itemIdx) => (
                    <ItineraryItem
                      key={item.id}
                      item={item}
                      isLast={itemIdx === dayItems.length - 1}
                      budgetCurrency={budgetCurrency}
                      {...replaceProps}
                    />
                  ))}
                </div>

                {/* Ask concierge chip */}
                <div className="px-5 pb-4">
                  <motion.button
                    whileHover={{ x: 2 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => onAskConcierge(day)}
                    className="inline-flex items-center gap-1.5 text-xs text-ink-400 hover:text-accent transition-colors py-1.5 px-3 rounded-full border border-ink-900/10 hover:border-accent/30 hover:bg-accent-tint"
                  >
                    <Compass className="w-3 h-3" />
                    Ask Concierge about Day {day} →
                  </motion.button>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}

export function EmptyItineraryState({ tripStatus }: { tripStatus: string }) {
  if (tripStatus === "planning" || tripStatus === "failed") return null;
  return (
    <Card className="p-10 text-center">
      <Loader2 className="w-8 h-8 text-accent animate-spin mx-auto mb-3" />
      <p className="text-ink-400 text-sm">
        {tripStatus === "generating" ? "Building your itinerary…" : "No items yet. Items will appear here once the agents finish."}
      </p>
    </Card>
  );
}
