"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  Compass, MapPin, Calendar, Users, DollarSign, Sparkles, Clock,
  CheckCircle2, AlertCircle, Loader2, ArrowRight, ChevronRight,
  Send, X, Hotel, Star, Wallet, Activity, Utensils, Bus,
  Sun, CloudRain, Wind, ZapIcon, Luggage, ChevronDown,
  Share2, Check, Pencil, Trash2, CalendarPlus, CalendarDays, Download,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  TripOut, ItineraryItemOut, ApprovalOut, ChatResponse, ChatSource,
  WeatherDay, HotelCandidateOut, TripUpdate,
} from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import NavBar from "@/components/ui/NavBar";

// ── TripMap (dynamic, no SSR) ─────────────────────────────────────────────────

const TripMap = dynamic(() => import("./TripMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[300px] rounded-2xl bg-space-800 animate-pulse flex items-center justify-center">
      <Loader2 className="w-6 h-6 text-electric-400 animate-spin" />
    </div>
  ),
});

// ── Types ─────────────────────────────────────────────────────────────────────

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
};

type IconComponent = LucideIcon;

// Extended TripOut to allow for fields the API may return that aren't in the base type
type TripOutExtended = TripOut & {
  agent_messages?: { role: string; content: string }[];
  budget_state?: {
    lodging?: number;
    activities?: number;
    meals?: number;
    transport?: number;
    total?: number;
    currency?: string;
    deviation_pct?: number;
  };
};

// ── Status config ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: IconComponent; glow: string }
> = {
  planning: {
    label: "Planning",
    color: "text-gold-400 bg-gold-500/10 border-gold-500/20",
    icon: Clock,
    glow: "shadow-gold-sm",
  },
  generating: {
    label: "Generating…",
    color: "text-electric-400 bg-electric-500/10 border-electric-500/20",
    icon: Loader2,
    glow: "shadow-electric-sm",
  },
  awaiting_approval: {
    label: "Your Call",
    color: "text-coral-400 bg-coral-500/10 border-coral-500/20",
    icon: AlertCircle,
    glow: "shadow-coral-sm",
  },
  planned: {
    label: "Ready",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    icon: CheckCircle2,
    glow: "",
  },
  failed: {
    label: "Failed",
    color: "text-coral-400 bg-coral-500/10 border-coral-500/20",
    icon: AlertCircle,
    glow: "",
  },
  cancelled: {
    label: "Cancelled",
    color: "text-slate-400 bg-slate-700/30 border-slate-700/30",
    icon: X,
    glow: "",
  },
};

// ── Item icons ─────────────────────────────────────────────────────────────────

const ITEM_ICONS: Record<string, { emoji: string; icon: IconComponent; color: string }> = {
  activity: { emoji: "🎭", icon: Activity,  color: "text-electric-400" },
  meal:     { emoji: "🍽",  icon: Utensils,  color: "text-gold-400"     },
  transport:{ emoji: "🚌", icon: Bus,       color: "text-emerald-400"  },
  lodging:  { emoji: "🏨", icon: Hotel,     color: "text-coral-400"    },
  free:     { emoji: "☀️", icon: Sun,       color: "text-gold-400"     },
};

// ── Destination gradient helper ───────────────────────────────────────────────

const DEST_GRADIENTS = [
  "from-sky-400 via-cyan-500 to-blue-600",
  "from-amber-400 via-orange-500 to-rose-500",
  "from-emerald-400 via-teal-500 to-cyan-600",
  "from-rose-400 via-pink-500 to-fuchsia-600",
  "from-indigo-400 via-blue-500 to-sky-600",
  "from-orange-400 via-amber-500 to-yellow-500",
];

function destGradient(city: string): string {
  let hash = 0;
  for (let i = 0; i < city.length; i++) hash = city.charCodeAt(i) + ((hash << 5) - hash);
  return DEST_GRADIENTS[Math.abs(hash) % DEST_GRADIENTS.length];
}

// ── Weather icon helper ────────────────────────────────────────────────────────

function WeatherIcon({ code, adverse }: { code: number; adverse: boolean }) {
  if (adverse || code >= 60) return <CloudRain className="w-4 h-4 text-blue-400" />;
  if (code >= 40) return <Wind className="w-4 h-4 text-slate-400" />;
  if (code >= 1) return <ZapIcon className="w-4 h-4 text-gold-400" />;
  return <Sun className="w-4 h-4 text-gold-400" />;
}

// ── SVG Donut Chart ────────────────────────────────────────────────────────────

interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

function DonutChart({ slices, currency }: { slices: DonutSlice[]; currency?: string }) {
  const total = slices.reduce((s, d) => s + d.value, 0);
  if (total === 0) return null;

  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-6">
      <svg width="140" height="140" viewBox="0 0 140 140" className="shrink-0">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="18" />
        {slices.map((slice) => {
          const pct = slice.value / total;
          const dashLen = pct * circumference;
          const thisOffset = offset;
          offset += dashLen;
          return (
            <circle
              key={slice.label}
              cx="70"
              cy="70"
              r={radius}
              fill="none"
              stroke={slice.color}
              strokeWidth="18"
              strokeDasharray={`${dashLen} ${circumference - dashLen}`}
              strokeDashoffset={-thisOffset + circumference * 0.25}
              strokeLinecap="round"
              style={{ transition: "stroke-dasharray 0.6s ease" }}
            />
          );
        })}
        <text x="70" y="65" textAnchor="middle" fontSize="11" fill="rgba(255,255,255,0.4)" fontFamily="inherit">
          Total
        </text>
        <text x="70" y="84" textAnchor="middle" fontSize="13" fill="white" fontWeight="600" fontFamily="inherit">
          {currency ?? ""} {total.toLocaleString()}
        </text>
      </svg>

      <div className="flex flex-col gap-2 min-w-0">
        {slices.map((slice) => (
          <div key={slice.label} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: slice.color }} />
            <span className="text-xs text-slate-400 flex-1">{slice.label}</span>
            <span className="text-xs text-slate-200 tabular-nums font-medium">
              {currency} {slice.value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Agent Pipeline ─────────────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  "Travel Style",
  "Itinerary Planner",
  "Hotels",
  "Budget",
  "Events",
  "Packing List",
  "Validation",
  "Saved",
];

function AgentPipeline({ messages }: { messages?: { role: string; content: string }[] }) {
  const activeStep = Math.min(
    Math.floor(((messages?.length ?? 0) / 3)),
    PIPELINE_STEPS.length - 1,
  );

  return (
    <div className="glass-card p-8 text-center">
      {/* Animated orb */}
      <div className="relative inline-flex w-20 h-20 mb-8">
        <div className="absolute inset-0 rounded-full bg-electric-gradient animate-pulse-glow" />
        <div className="absolute inset-1 rounded-full bg-space-800 flex items-center justify-center">
          <Sparkles className="w-8 h-8 text-electric-400 animate-pulse" />
        </div>
      </div>

      <h2 className="text-xl font-bold text-white mb-1">Building Your Journey</h2>
      <p className="text-sm text-slate-500 mb-10">
        AI agents are crafting a personalised itinerary. This usually takes 30–60 s.
      </p>

      {/* Pipeline steps */}
      <div className="flex items-center justify-center gap-0 mb-10 flex-wrap gap-y-4">
        {PIPELINE_STEPS.map((step, i) => {
          const done = i < activeStep;
          const active = i === activeStep;
          return (
            <div key={step} className="flex items-center">
              <div className="flex flex-col items-center gap-1.5">
                <motion.div
                  animate={active ? { scale: [1, 1.08, 1] } : {}}
                  transition={{ repeat: Infinity, duration: 1.4 }}
                  className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all duration-500 ${
                    done
                      ? "bg-emerald-500/20 border-emerald-500/60 text-emerald-400"
                      : active
                      ? "bg-electric-500/20 border-electric-500/60 text-electric-400 shadow-electric-sm"
                      : "bg-space-700 border-ink-900/10 text-slate-600"
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : active ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <div className="w-1.5 h-1.5 rounded-full bg-current" />
                  )}
                </motion.div>
                <span
                  className={`text-[10px] font-medium whitespace-nowrap ${
                    done
                      ? "text-emerald-400"
                      : active
                      ? "text-electric-400"
                      : "text-slate-600"
                  }`}
                >
                  {step}
                </span>
              </div>

              {i < PIPELINE_STEPS.length - 1 && (
                <div
                  className={`w-8 h-px mx-1 mb-5 transition-all duration-700 ${
                    done ? "bg-emerald-500/60" : "bg-ink-900/[0.06]"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Live message stream */}
      {messages && messages.length > 0 && (
        <div className="glass-light rounded-xl p-4 max-h-32 overflow-y-auto text-left space-y-1.5">
          {messages.slice(-6).map((msg, i) => (
            <p key={i} className="text-xs text-slate-400 leading-relaxed">
              <span className="text-electric-400 font-medium">{msg.role}:</span>{" "}
              {msg.content}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Weather Timeline strip ─────────────────────────────────────────────────────

function WeatherTimeline({ days }: { days: WeatherDay[] }) {
  if (!days.length) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-0.5 scrollbar-hide">
      {days.slice(0, 7).map((d) => (
        <div
          key={d.date}
          className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl shrink-0 ${
            d.is_adverse
              ? "bg-coral-500/10 border border-coral-500/20"
              : "bg-ink-900/[0.04] border border-ink-900/10"
          }`}
        >
          <span className="text-[10px] text-slate-500">
            {new Date(d.date + "T00:00:00").toLocaleDateString("en-US", {
              weekday: "short",
            })}
          </span>
          <WeatherIcon code={d.condition_code} adverse={d.is_adverse} />
          <span className="text-[10px] text-slate-300 tabular-nums">
            {Math.round(d.temp_max_c)}°
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Day Nav sidebar ────────────────────────────────────────────────────────────

function DayNav({
  days,
  activeDay,
  onSelect,
}: {
  days: number[];
  activeDay: number;
  onSelect: (d: number) => void;
}) {
  return (
    <nav className="flex flex-col gap-1">
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-2 px-2">
        Days
      </p>
      {days.map((d) => (
        <button
          key={d}
          onClick={() => onSelect(d)}
          className={`w-full text-left px-3 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
            d === activeDay
              ? "bg-electric-500/15 border border-electric-500/30 text-electric-400"
              : "text-slate-500 hover:text-slate-300 hover:bg-ink-900/[0.04]"
          }`}
        >
          Day {d}
        </button>
      ))}
    </nav>
  );
}

// ── Edit Trip Modal ────────────────────────────────────────────────────────────

function EditTripModal({
  trip,
  onClose,
  onSave,
}: {
  trip: TripOut;
  onClose: () => void;
  onSave: (updates: TripUpdate) => Promise<void>;
}) {
  const [form, setForm] = useState<TripUpdate>({
    title: trip.title,
    destination_city: trip.destination_city,
    destination_country: trip.destination_country ?? "",
    start_date: trip.start_date,
    end_date: trip.end_date,
    num_travelers: trip.num_travelers,
    budget_total: trip.budget_total ?? undefined,
    budget_currency: trip.budget_currency,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof TripUpdate, value: unknown) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave(form);
      onClose();
    } catch {
      setError("Could not save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const fieldCls = "w-full bg-space-800 border border-ink-900/10 rounded-xl px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-electric-500/50 transition-colors";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0, y: 8 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.95, opacity: 0, y: 8 }}
        transition={{ type: "spring", damping: 28, stiffness: 340 }}
        className="glass-card p-6 w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-slate-100">Edit Trip</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-ink-900/[0.04] transition-all">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Trip name</label>
            <input className={fieldCls} value={form.title ?? ""} onChange={(e) => set("title", e.target.value)} required />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-500 mb-1 block">City</label>
              <input className={fieldCls} value={form.destination_city ?? ""} onChange={(e) => set("destination_city", e.target.value)} required />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Country</label>
              <input className={fieldCls} placeholder="Optional" value={form.destination_country ?? ""} onChange={(e) => set("destination_country", e.target.value || null)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Start date</label>
              <input type="date" className={fieldCls} value={form.start_date ?? ""} onChange={(e) => set("start_date", e.target.value)} required />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">End date</label>
              <input type="date" className={fieldCls} value={form.end_date ?? ""} onChange={(e) => set("end_date", e.target.value)} required />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Travelers</label>
              <input type="number" min={1} max={20} className={fieldCls} value={form.num_travelers ?? 1} onChange={(e) => set("num_travelers", parseInt(e.target.value))} required />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Budget</label>
              <input type="number" min={0} className={fieldCls} placeholder="Optional" value={form.budget_total ?? ""} onChange={(e) => set("budget_total", e.target.value ? parseFloat(e.target.value) : null)} />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-500 mb-1 block">Currency</label>
            <input className={`${fieldCls} uppercase`} maxLength={3} value={form.budget_currency ?? "USD"} onChange={(e) => set("budget_currency", e.target.value.toUpperCase())} />
          </div>

          {error && <p className="text-xs text-coral-400">{error}</p>}

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-ink-900/10 hover:bg-ink-900/[0.04] transition-colors">
              Cancel
            </button>
            <motion.button
              type="submit"
              whileTap={{ scale: 0.97 }}
              disabled={saving}
              className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-electric-gradient text-white shadow-electric-sm hover:shadow-electric transition-all disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save changes"}
            </motion.button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}

// ── Approval Cards ─────────────────────────────────────────────────────────────

type OnDecision = (id: string, decision: "approved" | "rejected", resolutionNote?: string) => void;

// ── ConciergeSwapCard ──────────────────────────────────────────────────────────

function ConciergeSwapCard({ approval, onDecision }: { approval: ApprovalOut; onDecision: OnDecision }) {
  const a = approval;
  const alternatives = (a.payload.alternatives as Array<{ title: string; description: string }> | undefined) ?? [];
  const [selectedAlt, setSelectedAlt] = useState(0);
  const current = a.payload.current as { title: string; item_type?: string; start_time?: string; est_cost?: number };
  const chosen = alternatives[selectedAlt] ?? (a.payload.replacement as { title: string; description?: string });

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold text-electric-400 bg-electric-500/10 border border-electric-500/20">
          AI Concierge
        </span>
        <span className="text-[10px] text-slate-500">Suggestion · Day {a.payload.day as number}</span>
      </div>

      {/* Before → After diff */}
      <div className="flex items-start gap-2 mb-3">
        <div className="flex-1 p-2.5 rounded-xl bg-ink-900/[0.03] border border-ink-900/10">
          <p className="text-[10px] text-slate-500 mb-0.5">Current</p>
          <p className="text-xs text-slate-400 line-through leading-snug">{current.title}</p>
          {current.start_time && (
            <p className="text-[10px] text-slate-600 mt-0.5">{current.start_time.slice(0, 5)}</p>
          )}
          {current.est_cost != null && (
            <p className="text-[10px] text-slate-600">{current.est_cost}</p>
          )}
        </div>
        <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0 mt-3.5" />
        <div className="flex-1 p-2.5 rounded-xl bg-electric-500/5 border border-electric-500/20">
          <p className="text-[10px] text-electric-400 mb-0.5">Proposed</p>
          <p className="text-xs text-slate-200 font-medium leading-snug">{chosen.title}</p>
          {chosen.description && (
            <p className="text-[10px] text-slate-500 line-clamp-2 mt-0.5">{chosen.description}</p>
          )}
        </div>
      </div>

      {/* Alternatives selector */}
      {alternatives.length > 1 && (
        <div className="mb-3 space-y-1.5">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest">Choose an option</p>
          {alternatives.map((alt, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedAlt(idx)}
              className={`w-full text-left px-3 py-2 rounded-xl text-xs transition-all border ${
                idx === selectedAlt
                  ? "bg-electric-500/15 border-electric-500/30 text-slate-100"
                  : "bg-ink-900/[0.03] border-ink-900/10 text-slate-400 hover:bg-ink-900/[0.04]"
              }`}
            >
              <span className="font-medium">{alt.title}</span>
              {alt.description && (
                <span className="text-[10px] text-slate-500 block line-clamp-1 mt-0.5">{alt.description}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {!!a.payload.reason && (
        <p className="text-xs text-slate-500 italic mb-4">{a.payload.reason as string}</p>
      )}

      <div className="flex gap-2">
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => onDecision(a.id, "approved", alternatives.length > 1 ? `alt:${selectedAlt}` : undefined)}
          className="text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-4 py-2 rounded-xl hover:bg-emerald-500/25 transition-colors font-medium"
        >
          Accept swap
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => onDecision(a.id, "rejected")}
          className="text-xs bg-ink-900/[0.04] text-slate-400 border border-ink-900/10 px-4 py-2 rounded-xl hover:bg-ink-900/[0.06] transition-colors"
        >
          Keep original
        </motion.button>
      </div>
    </div>
  );
}

// ── ConciergeAddCard ───────────────────────────────────────────────────────────

function ConciergeAddCard({ approval, onDecision }: { approval: ApprovalOut; onDecision: OnDecision }) {
  const a = approval;
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20">
          AI Concierge
        </span>
        <span className="text-[10px] text-slate-500">Day {a.payload.day as number} · Add</span>
      </div>
      <p className="font-semibold text-slate-100 text-sm leading-snug mb-0.5">
        {a.payload.title as string}
      </p>
      {!!a.payload.description && (
        <p className="text-xs text-slate-500 line-clamp-2 mb-1">
          {a.payload.description as string}
        </p>
      )}
      {!!a.payload.reason && (
        <p className="text-xs text-slate-500 italic mb-4">{a.payload.reason as string}</p>
      )}
      <div className="flex gap-2">
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => onDecision(a.id, "approved")}
          className="text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-4 py-2 rounded-xl hover:bg-emerald-500/25 transition-colors font-medium"
        >
          Add to itinerary
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => onDecision(a.id, "rejected")}
          className="text-xs bg-ink-900/[0.04] text-slate-400 border border-ink-900/10 px-4 py-2 rounded-xl hover:bg-ink-900/[0.06] transition-colors"
        >
          No thanks
        </motion.button>
      </div>
    </div>
  );
}

// ── ApprovalCard (dispatcher) ──────────────────────────────────────────────────

function ApprovalCard({
  approval,
  onDecision,
}: {
  approval: ApprovalOut;
  onDecision: OnDecision;
}) {
  const a = approval;

  if (a.change_type === "event_add") {
    return (
      <div className="glass-card p-4">
        <div className="flex gap-3">
          {/* Event source badge + category */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-1">
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                  a.payload.source === "ticketmaster"
                    ? "text-electric-400 bg-electric-500/10 border-electric-500/20"
                    : "text-purple-400 bg-purple-500/10 border-purple-500/20"
                }`}
              >
                {a.payload.source === "ticketmaster" ? "Ticketmaster" : "Eventbrite"}
              </span>
              <span className="text-[10px] text-slate-500">{a.payload.category as string}</span>
            </div>
            <p className="font-semibold text-slate-100 text-sm leading-snug">
              {a.payload.event_name as string}
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              Day {a.payload.day_number as number} · {a.payload.venue_name as string}
            </p>
            {!!a.payload.start_time && (
              <p className="text-xs text-slate-600">{String(a.payload.start_time)}</p>
            )}
            {a.payload.price_min != null && (
              <p className="text-xs text-gold-400 mt-0.5 font-medium">
                {a.payload.price_currency as string}{" "}
                {(a.payload.price_min as number).toFixed(0)}
                {a.payload.price_max !== a.payload.price_min
                  ? `–${(a.payload.price_max as number).toFixed(0)}`
                  : ""}
              </p>
            )}
            <p className="text-xs text-slate-500 mt-1.5 line-clamp-2">{a.summary}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 mt-4">
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => onDecision(a.id, "approved")}
            className="text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-4 py-2 rounded-xl hover:bg-emerald-500/25 transition-colors font-medium"
          >
            Add to itinerary
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => onDecision(a.id, "rejected")}
            className="text-xs bg-ink-900/[0.04] text-slate-400 border border-ink-900/10 px-4 py-2 rounded-xl hover:bg-ink-900/[0.06] transition-colors"
          >
            Skip
          </motion.button>
          {!!a.payload.url && (
            <a
              href={String(a.payload.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-electric-400 hover:underline ml-auto"
            >
              View ↗
            </a>
          )}
        </div>
      </div>
    );
  }

  if (a.change_type === "budget_swap") {
    return (
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold text-coral-400 bg-coral-500/10 border border-coral-500/20">
            Over Budget
          </span>
          <span className="text-[10px] text-slate-500">Budget Optimizer</span>
        </div>
        <div className="space-y-1 mb-3">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="line-through">
              {(a.payload.current as { title: string }).title}
              {a.payload.est_cost_original != null
                ? ` · ${a.payload.currency as string} ${(a.payload.est_cost_original as number).toFixed(0)}`
                : ""}
            </span>
            <ArrowRight className="w-3 h-3 text-slate-600 shrink-0" />
            <span className="text-slate-200 font-medium">
              {(a.payload.replacement as { title: string }).title}
            </span>
          </div>
          {(a.payload.replacement as { description?: string }).description && (
            <p className="text-xs text-slate-500 line-clamp-2">
              {(a.payload.replacement as { description: string }).description}
            </p>
          )}
        </div>
        <p className="text-xs text-slate-500 italic mb-4">{a.payload.reason as string}</p>
        <div className="flex gap-2">
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => onDecision(a.id, "approved")}
            className="text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-4 py-2 rounded-xl hover:bg-emerald-500/25 transition-colors font-medium"
          >
            Accept swap
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => onDecision(a.id, "rejected")}
            className="text-xs bg-ink-900/[0.04] text-slate-400 border border-ink-900/10 px-4 py-2 rounded-xl hover:bg-ink-900/[0.06] transition-colors"
          >
            Keep original
          </motion.button>
        </div>
      </div>
    );
  }

  if (a.change_type === "budget_upgrade") {
    return (
      <div className="glass-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20">
            Under Budget
          </span>
          <span className="text-[10px] text-slate-500">Budget Optimizer</span>
          {a.payload.budget_remaining != null && (
            <span className="text-[10px] text-slate-500 ml-auto">
              {a.payload.currency as string}{" "}
              {(a.payload.budget_remaining as number).toFixed(0)} remaining
            </span>
          )}
        </div>
        <p className="font-semibold text-slate-100 text-sm mb-0.5">{String(a.payload.title ?? "")}</p>
        {!!a.payload.description && (
          <p className="text-xs text-slate-500 line-clamp-2 mb-1">
            {String(a.payload.description)}
          </p>
        )}
        <p className="text-xs text-slate-500 italic mb-4">{String(a.payload.reason ?? "")}</p>
        <div className="flex gap-2">
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => onDecision(a.id, "approved")}
            className="text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-4 py-2 rounded-xl hover:bg-emerald-500/25 transition-colors font-medium"
          >
            Sounds great
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => onDecision(a.id, "rejected")}
            className="text-xs bg-ink-900/[0.04] text-slate-400 border border-ink-900/10 px-4 py-2 rounded-xl hover:bg-ink-900/[0.06] transition-colors"
          >
            Not interested
          </motion.button>
        </div>
      </div>
    );
  }

  if (a.change_type === "concierge_swap") {
    return <ConciergeSwapCard approval={a} onDecision={onDecision} />;
  }

  if (a.change_type === "concierge_add") {
    return <ConciergeAddCard approval={a} onDecision={onDecision} />;
  }

  // Generic fallback
  return (
    <div className="glass-card p-4">
      <p className="text-[10px] text-electric-400 uppercase tracking-widest mb-1 font-semibold">
        {a.change_type.replace(/_/g, " ")}
      </p>
      <p className="text-sm text-slate-300 mb-4">{a.summary}</p>
      <div className="flex gap-2">
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => onDecision(a.id, "approved")}
          className="text-xs bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-4 py-2 rounded-xl hover:bg-emerald-500/25 transition-colors font-medium"
        >
          Approve
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => onDecision(a.id, "rejected")}
          className="text-xs bg-ink-900/[0.04] text-slate-400 border border-ink-900/10 px-4 py-2 rounded-xl hover:bg-ink-900/[0.06] transition-colors"
        >
          Reject
        </motion.button>
      </div>
    </div>
  );
}

// ── Packing List Panel ────────────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, string> = {
  "Documents & Money": "📄",
  Clothing: "👕",
  Electronics: "⚡",
  "Health & Toiletries": "💊",
  Accessories: "🎒",
  "Destination-Specific": "📍",
};

function PackingListPanel({
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
      if (next.has(item)) { next.delete(item); } else { next.add(item); }
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
      <div className="flex items-center gap-2 mb-4">
        <Luggage className="w-4 h-4 text-emerald-400" />
        <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">
          Packing List
        </h2>
        <span className="ml-auto text-xs text-slate-500">
          {checkedCount}/{totalItems} packed
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4 h-1.5 bg-ink-900/[0.04] rounded-full overflow-hidden">
        <motion.div
          className="h-full bg-emerald-500 rounded-full"
          animate={{ width: `${totalItems > 0 ? (checkedCount / totalItems) * 100 : 0}%` }}
          transition={{ duration: 0.4 }}
        />
      </div>

      <div className="glass-card overflow-hidden">
        {/* Toggle header */}
        <button
          onClick={() => setOpen((v) => !v)}
          className="w-full flex items-center justify-between px-5 py-4 hover:bg-ink-900/[0.03] transition-colors"
        >
          <span className="text-sm text-slate-400">
            {open ? "Hide checklist" : `Show ${totalItems} items across ${Object.keys(packingList.categories).length} categories`}
          </span>
          <ChevronDown
            className={`w-4 h-4 text-slate-500 transition-transform duration-300 ${open ? "rotate-180" : ""}`}
          />
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              key="packing-body"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <div className="px-5 pb-5 space-y-5 border-t border-ink-900/8">
                {Object.entries(packingList.categories).map(([cat, items]) => (
                  <div key={cat} className="pt-4">
                    <div className="flex items-center gap-2 mb-2.5">
                      <span className="text-base">{CATEGORY_ICONS[cat] ?? "📦"}</span>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
                        {cat}
                      </p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {items.map((item) => (
                        <button
                          key={item}
                          onClick={() => toggle(item)}
                          className={`flex items-center gap-2.5 text-left px-3 py-2 rounded-xl transition-all text-xs ${
                            checked.has(item)
                              ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                              : "bg-ink-900/[0.03] border border-ink-900/8 text-slate-400 hover:bg-ink-900/[0.05] hover:text-slate-300"
                          }`}
                        >
                          <div
                            className={`w-4 h-4 rounded-md border shrink-0 flex items-center justify-center transition-all ${
                              checked.has(item)
                                ? "bg-emerald-500 border-emerald-500"
                                : "border-ink-900/15"
                            }`}
                          >
                            {checked.has(item) && <CheckCircle2 className="w-2.5 h-2.5 text-white" />}
                          </div>
                          <span className={checked.has(item) ? "line-through opacity-60" : ""}>
                            {item}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.section>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TripDetailPage() {
  const { tripId } = useParams<{ tripId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, _hasHydrated } = useAuthStore();

  useEffect(() => {
    if (_hasHydrated && !token) router.replace("/login");
  }, [_hasHydrated, token, router]);

  // ── Queries ──────────────────────────────────────────────────────────────────

  const { data: tripRaw, isLoading: tripLoading } = useQuery<TripOut>({
    queryKey: ["trip", tripId],
    queryFn: () => api.get<TripOut>(`/api/v1/trips/${tripId}`),
    refetchInterval: (q) => (q.state.data?.status === "generating" ? 2000 : false),
    enabled: !!token && !!tripId,
  });
  const trip = tripRaw as TripOutExtended | undefined;

  const { data: weatherDays = [] } = useQuery<WeatherDay[]>({
    queryKey: ["weather", tripId],
    queryFn: () => api.get<WeatherDay[]>(`/api/v1/trips/${tripId}/weather`),
    enabled: !!token && !!tripId,
    staleTime: 30 * 60 * 1000,
  });

  const { data: items = [] } = useQuery<ItineraryItemOut[]>({
    queryKey: ["itinerary", tripId],
    queryFn: () => api.get<ItineraryItemOut[]>(`/api/v1/trips/${tripId}/itinerary`),
    enabled: !!trip && trip.status !== "planning",
    staleTime: 10_000,
  });

  const { data: hotels = [] } = useQuery<HotelCandidateOut[]>({
    queryKey: ["hotels", tripId],
    queryFn: () => api.get<HotelCandidateOut[]>(`/api/v1/trips/${tripId}/hotels`),
    enabled: !!token && !!tripId && !!trip && trip.status !== "planning",
    staleTime: 60_000,
  });

  const { data: pendingApprovals = [] } = useQuery<ApprovalOut[]>({
    queryKey: ["approvals", tripId, "pending"],
    queryFn: () =>
      api.get<ApprovalOut[]>(`/api/v1/trips/${tripId}/approvals`, { status: "pending" }),
    enabled: trip?.status === "awaiting_approval",
  });

  // Status transition cache invalidation
  const prevStatusRef = useRef<string | undefined>();
  useEffect(() => {
    const prev = prevStatusRef.current;
    const curr = trip?.status;
    prevStatusRef.current = curr;
    if (!prev || prev === curr) return;
    if (curr === "planned" || curr === "awaiting_approval") {
      // Generation rebuilds itinerary, hotels and weather — refetch all of them, not
      // just the itinerary, so the (re)selected hotel and forecast aren't left stale
      // (the hotels query often resolves empty mid-generation and would never refresh).
      queryClient.invalidateQueries({ queryKey: ["itinerary", tripId] });
      queryClient.invalidateQueries({ queryKey: ["hotels", tripId] });
      queryClient.invalidateQueries({ queryKey: ["weather", tripId] });
    }
    if (curr === "awaiting_approval") {
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
    }
  }, [trip?.status, queryClient, tripId]);

  // ── Share ─────────────────────────────────────────────────────────────────────

  const [shareLoading, setShareLoading] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  async function handleShare() {
    if (!trip) return;
    setShareLoading(true);
    try {
      let token = trip.share_token;
      if (!token) {
        const updated = await api.createShareLink(trip.id);
        token = updated.share_token;
        queryClient.setQueryData(["trip", tripId], updated);
      }
      const url = `${window.location.origin}/share/${token}`;
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2500);
    } finally {
      setShareLoading(false);
    }
  }

  // ── Edit ──────────────────────────────────────────────────────────────────────

  const [editOpen, setEditOpen] = useState(false);

  async function handleEditSave(updates: TripUpdate) {
    const updated = await api.updateTrip(tripId, updates);
    queryClient.setQueryData(["trip", tripId], updated);
  }

  // ── Delete ────────────────────────────────────────────────────────────────────

  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.deleteTrip(tripId);
      router.replace("/trips");
    } finally {
      setDeleting(false);
    }
  }

  // ── Calendar export ───────────────────────────────────────────────────────────

  const [calendarOpen, setCalendarOpen] = useState(false);
  const [icsLoading, setIcsLoading] = useState(false);

  function handleGoogleCalendar() {
    if (!trip) return;
    const start = trip.start_date.replace(/-/g, "");
    const end = trip.end_date.replace(/-/g, "");
    const url = new URL("https://calendar.google.com/calendar/render");
    url.searchParams.set("action", "TEMPLATE");
    url.searchParams.set("text", `Trip to ${trip.destination_city}`);
    url.searchParams.set("dates", `${start}/${end}`);
    url.searchParams.set("details", `AI-planned itinerary by TravelOS`);
    url.searchParams.set("location", [trip.destination_city, trip.destination_country].filter(Boolean).join(", "));
    window.open(url.toString(), "_blank", "noopener,noreferrer");
    setCalendarOpen(false);
  }

  async function handleDownloadIcs() {
    if (!trip || icsLoading) return;
    setIcsLoading(true);
    try {
      await api.downloadCalendarIcs(trip.id, trip.destination_city);
    } finally {
      setIcsLoading(false);
      setCalendarOpen(false);
    }
  }

  // ── Generate ─────────────────────────────────────────────────────────────────

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    try {
      await api.post(`/api/v1/trips/${tripId}/itinerary/generate`);
      // Optimistically flip to "generating" so the trip query's refetchInterval starts
      // polling and the status-transition effect refreshes the itinerary once the worker
      // finishes. An immediate refetch can race and read the stale "planned" status,
      // which would leave polling off and the UI stuck on the old plan.
      queryClient.setQueryData<TripOut>(["trip", tripId], (old) =>
        old ? { ...old, status: "generating" } : old,
      );
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { message?: string } | null;
        setGenerateError(detail?.message ?? `Error ${err.status}`);
      } else {
        setGenerateError("Could not start generation. Is the backend running?");
      }
    } finally {
      setGenerating(false);
    }
  }

  // ── Approvals ─────────────────────────────────────────────────────────────────

  async function handleDecision(
    approvalId: string,
    decision: "approved" | "rejected",
    resolutionNote?: string,
  ) {
    try {
      await api.post(`/api/v1/approvals/${approvalId}`, {
        decision,
        ...(resolutionNote ? { resolution_note: resolutionNote } : {}),
      });
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
      queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
      queryClient.invalidateQueries({ queryKey: ["itinerary", tripId] });
    } catch {
      // silently ignore — stale UI will auto-refresh on next poll
    }
  }

  // ── Replace ───────────────────────────────────────────────────────────────────

  const [replaceTarget, setReplaceTarget] = useState<string | null>(null);
  const [replaceTitle, setReplaceTitle] = useState("");
  const [replaceLoading, setReplaceLoading] = useState(false);

  async function handleReplace(itemId: string) {
    const title = replaceTitle.trim();
    if (!title || replaceLoading) return;
    setReplaceLoading(true);
    try {
      await api.post(`/api/v1/trips/${tripId}/approvals`, {
        item_id: itemId,
        replacement_title: title,
      });
      setReplaceTarget(null);
      setReplaceTitle("");
      queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
    } catch {
      // leave form open on error
    } finally {
      setReplaceLoading(false);
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────────

  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function sendMessage(userText: string): Promise<void> {
    try {
      const res = await api.post<ChatResponse>(`/api/v1/trips/${tripId}/chat`, {
        question: userText,
      });
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", text: res.answer, sources: res.sources },
      ]);
      if (res.proposal_id) {
        queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
        queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Sorry, I couldn't answer that right now. Please try again." },
      ]);
    }
  }

  async function handleChatSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", text: q }]);
    setChatLoading(true);
    try {
      await sendMessage(q);
    } finally {
      setChatLoading(false);
    }
  }

  // ── Day navigation via IntersectionObserver ────────────────────────────────

  const [activeDay, setActiveDay] = useState(1);
  const daySectionRefs = useRef<Record<number, HTMLElement | null>>({});

  const setDaySectionRef = useCallback(
    (day: number) => (el: HTMLElement | null) => {
      daySectionRefs.current[day] = el;
    },
    [],
  );

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const day = Number((entry.target as HTMLElement).dataset.day);
            if (day) setActiveDay(day);
          }
        }
      },
      { threshold: 0.4 },
    );

    const refs = daySectionRefs.current;
    Object.values(refs).forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, [items]);

  function scrollToDay(day: number) {
    daySectionRefs.current[day]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ── Derived values ────────────────────────────────────────────────────────────

  const nights = trip
    ? Math.ceil(
        (new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) /
          (1000 * 60 * 60 * 24),
      )
    : 0;

  const itemsByDay = items.reduce<Record<number, ItineraryItemOut[]>>((acc, item) => {
    (acc[item.day_number] ??= []).push(item);
    return acc;
  }, {});

  const dayNumbers = Object.keys(itemsByDay)
    .map(Number)
    .sort((a, b) => a - b);

  const pinnedItems = items.filter((i) => i.latitude != null && i.longitude != null);

  const selectedHotel = hotels.find((h) => h.is_selected);
  const otherHotels = hotels.filter((h) => !h.is_selected);

  const budgetSlices: { label: string; value: number; color: string }[] = trip?.budget_state
    ? [
        { label: "Lodging",    value: trip.budget_state.lodging    ?? 0, color: "#3b82f6" },
        { label: "Activities", value: trip.budget_state.activities ?? 0, color: "#a78bfa" },
        { label: "Meals",      value: trip.budget_state.meals      ?? 0, color: "#fbbf24" },
        { label: "Transport",  value: trip.budget_state.transport  ?? 0, color: "#34d399" },
      ].filter((s) => s.value > 0)
    : [];

  // ── Early returns ─────────────────────────────────────────────────────────────

  if (!_hasHydrated) return null;

  if (tripLoading) {
    return (
      <div className="min-h-screen bg-space-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-electric-400 animate-spin" />
          <p className="text-slate-500 text-sm">Loading trip…</p>
        </div>
      </div>
    );
  }

  if (!trip) {
    return (
      <div className="min-h-screen bg-space-900 flex flex-col items-center justify-center gap-4">
        <AlertCircle className="w-12 h-12 text-coral-400" />
        <p className="text-slate-400 text-sm">Trip not found.</p>
        <Link href="/trips">
          <button className="btn-primary text-sm py-2.5 px-5">Back to trips</button>
        </Link>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[trip.status] ?? STATUS_CONFIG.planned;
  const StatusIcon = statusCfg.icon as React.ComponentType<{ className?: string }>;
  const gradient = destGradient(trip.destination_city);

  // ── State A: Generating ────────────────────────────────────────────────────────

  if (trip.status === "generating") {
    return (
      <div className="min-h-screen bg-space-900">
        <NavBar />

        {/* Ambient glow */}
        <div className="fixed inset-0 pointer-events-none">
          <div className="absolute top-32 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-electric-500/5 rounded-full blur-3xl" />
        </div>

        <main className="relative z-10 max-w-2xl mx-auto px-4 pt-28 pb-16">
          <Link
            href="/trips"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors mb-8"
          >
            <ChevronRight className="w-3 h-3 rotate-180" />
            My trips
          </Link>

          <div className="mb-6 flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white flex-1">{trip.title}</h1>
            <span className={`status-badge border ${statusCfg.color}`}>
              <StatusIcon className="w-3 h-3 animate-spin" />
              {statusCfg.label}
            </span>
          </div>

          <AgentPipeline messages={trip.agent_messages} />
        </main>
      </div>
    );
  }

  // ── State B: Awaiting Approval ─────────────────────────────────────────────────

  if (trip.status === "awaiting_approval" && pendingApprovals.length > 0) {
    return (
      <div className="min-h-screen bg-space-900">
        <NavBar />

        {/* Ambient coral glow */}
        <div className="fixed inset-0 pointer-events-none">
          <div className="absolute top-24 left-1/2 -translate-x-1/2 w-[500px] h-[200px] bg-coral-500/5 rounded-full blur-3xl" />
        </div>

        {/* Sticky approval banner */}
        <div className="sticky top-16 z-40 border-b border-coral-500/20 bg-coral-500/10 backdrop-blur-glass">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
            <AlertCircle className="w-4 h-4 text-coral-400 shrink-0" />
            <p className="text-sm text-coral-600 font-medium flex-1">
              {pendingApprovals.length} change{pendingApprovals.length !== 1 ? "s" : ""} need
              {pendingApprovals.length === 1 ? "s" : ""} your review
            </p>
            <span className="text-xs text-coral-500">Scroll down to review</span>
          </div>
        </div>

        <main className="relative z-10 max-w-2xl mx-auto px-4 pt-8 pb-24">
          <Link
            href="/trips"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors mb-6"
          >
            <ChevronRight className="w-3 h-3 rotate-180" />
            My trips
          </Link>

          <div className="mb-8 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold text-white truncate">{trip.title}</h1>
              <p className="text-sm text-slate-500 mt-0.5">
                {trip.destination_city}
                {trip.destination_country ? `, ${trip.destination_country}` : ""} ·{" "}
                {nights} night{nights !== 1 ? "s" : ""}
              </p>
            </div>
            <span className={`status-badge border ${statusCfg.color} shrink-0`}>
              <StatusIcon className="w-3 h-3" />
              {statusCfg.label}
            </span>
          </div>

          <div className="space-y-3">
            {pendingApprovals.map((a, i) => (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
              >
                <ApprovalCard approval={a} onDecision={handleDecision} />
              </motion.div>
            ))}
          </div>
        </main>
      </div>
    );
  }

  // ── State C: Planned / Default ─────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-space-900">
      <NavBar />

      {/* Ambient background glows */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-72 bg-electric-500/4 rounded-full blur-3xl" />
        <div className="absolute top-48 right-1/4 w-64 h-48 bg-purple-600/4 rounded-full blur-3xl" />
      </div>

      {/* ── Hero Banner ────────────────────────────────────────────────────── */}
      <div
        className={`relative h-48 bg-gradient-to-br ${gradient} overflow-hidden`}
        style={trip.cover_image_url ? {
          backgroundImage: `url(${trip.cover_image_url})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        } : undefined}
      >
        {/* Overlay — heavier when photo is present for text legibility */}
        {trip.cover_image_url
          ? <div className="absolute inset-0 bg-gradient-to-t from-ink-900/90 via-ink-900/45 to-ink-900/10" />
          : <>
              <div className="absolute inset-0 opacity-15" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")` }} />
              <div className="absolute inset-0 bg-gradient-to-t from-ink-900/65 via-ink-900/10 to-transparent" />
            </>
        }

        {/* Hero content */}
        <div className="relative z-10 h-full flex flex-col justify-end px-4 pb-5 max-w-7xl mx-auto">
          {/* Breadcrumb */}
          <Link
            href="/trips"
            className="absolute top-5 left-4 inline-flex items-center gap-1.5 text-xs text-white/60 hover:text-white transition-colors"
          >
            <ChevronRight className="w-3 h-3 rotate-180" />
            My trips
          </Link>

          <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <MapPin className="w-4 h-4 text-white/70" />
                <span className="text-white/70 text-xs font-medium uppercase tracking-widest">
                  {trip.destination_country ?? ""}
                </span>
              </div>
              <h1 className="text-3xl lg:text-4xl font-bold text-white leading-tight">
                {trip.destination_city}
              </h1>
            </div>

            <div className="flex flex-col gap-2 lg:items-end">
              {/* Trip meta pills */}
              <div className="flex flex-wrap gap-2">
                <div className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/20">
                  <Calendar className="w-3 h-3" />
                  {new Date(trip.start_date + "T00:00:00").toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}{" "}
                  –{" "}
                  {new Date(trip.end_date + "T00:00:00").toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/20">
                  <Users className="w-3 h-3" />
                  {trip.num_travelers} traveler{trip.num_travelers !== 1 ? "s" : ""}
                </div>
                {trip.budget_total && (
                  <div className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/20">
                    <DollarSign className="w-3 h-3" />
                    {trip.budget_currency} {trip.budget_total.toLocaleString()}
                  </div>
                )}
                <span className={`status-badge border ${statusCfg.color}`}>
                  <StatusIcon
                    className={`w-3 h-3 ${trip.status === "generating" ? "animate-spin" : ""}`}
                  />
                  {statusCfg.label}
                </span>
                <button
                  onClick={handleShare}
                  disabled={shareLoading}
                  className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/15 transition-colors disabled:opacity-50"
                  title="Copy share link"
                >
                  {shareLoading ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : shareCopied ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Share2 className="w-3 h-3" />
                  )}
                  {shareCopied ? "Copied!" : "Share"}
                </button>

                {/* Calendar export */}
                <div className="relative">
                  <button
                    onClick={() => setCalendarOpen((v) => !v)}
                    className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/15 transition-colors"
                    title="Export to calendar"
                  >
                    <CalendarPlus className="w-3 h-3" />
                    Calendar
                  </button>
                  <AnimatePresence>
                    {calendarOpen && (
                      <motion.div
                        initial={{ opacity: 0, y: 6, scale: 0.96 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 6, scale: 0.96 }}
                        transition={{ duration: 0.15 }}
                        className="absolute top-full mt-2 left-0 w-44 glass-card py-1 z-20"
                      >
                        <button
                          onClick={handleGoogleCalendar}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-300 hover:bg-ink-900/[0.04] transition-colors"
                        >
                          <CalendarDays className="w-3.5 h-3.5 text-electric-400 shrink-0" />
                          Google Calendar
                        </button>
                        <button
                          onClick={handleDownloadIcs}
                          disabled={icsLoading}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-300 hover:bg-ink-900/[0.04] transition-colors disabled:opacity-50"
                        >
                          {icsLoading
                            ? <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                            : <Download className="w-3.5 h-3.5 text-gold-400 shrink-0" />
                          }
                          Download .ics
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Edit trip */}
                <button
                  onClick={() => setEditOpen(true)}
                  className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/15 transition-colors"
                  title="Edit trip"
                >
                  <Pencil className="w-3 h-3" />
                  Edit
                </button>

                {/* Delete trip */}
                <button
                  onClick={() => setDeleteConfirm(true)}
                  className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/20 hover:bg-coral-500/25 hover:text-white hover:border-coral-400 transition-colors"
                  title="Delete trip"
                >
                  <Trash2 className="w-3 h-3" />
                  Delete
                </button>
              </div>

              {/* Weather timeline strip */}
              {weatherDays.length > 0 && (
                <div className="mt-1">
                  <WeatherTimeline days={weatherDays} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Planning status / generate banner ──────────────────────────────── */}
      {(trip.status === "planning" || trip.status === "failed") && (
        <div className="max-w-7xl mx-auto px-4 pt-6">
          <div className="glass-card p-6 flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-5">
            <div className="w-12 h-12 rounded-2xl bg-electric-gradient flex items-center justify-center shrink-0 shadow-electric">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              {trip.status === "failed" ? (
                <>
                  <p className="text-sm font-semibold text-coral-400 mb-0.5">Generation failed</p>
                  {generateError && <p className="text-xs text-slate-500">{generateError}</p>}
                </>
              ) : (
                <>
                  <p className="text-sm font-semibold text-slate-200 mb-0.5">No itinerary yet</p>
                  <p className="text-xs text-slate-500">
                    Let TravelOS AI agents plan everything for you.
                  </p>
                </>
              )}
            </div>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleGenerate}
              disabled={generating}
              className="btn-primary flex items-center justify-center gap-2 w-full sm:w-auto whitespace-nowrap disabled:opacity-50"
            >
              {generating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              {generating ? "Queuing…" : trip.status === "failed" ? "Try again" : "Generate itinerary"}
            </motion.button>
          </div>
        </div>
      )}

      {/* ── Main 3-column layout ───────────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto px-4 pt-8 pb-32">
        <div className="flex gap-6 lg:gap-8 relative">

          {/* ── LEFT SIDEBAR: Day navigation ─────────────────────────────── */}
          {dayNumbers.length > 0 && (
            <div className="hidden lg:block w-[220px] shrink-0">
              <div className="sticky top-24">
                <DayNav days={dayNumbers} activeDay={activeDay} onSelect={scrollToDay} />

                {/* Quick links */}
                <div className="mt-6 space-y-1">
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-2 px-2">
                    Jump to
                  </p>
                  {hotels.length > 0 && (
                    <button
                      onClick={() =>
                        document
                          .getElementById("hotels-section")
                          ?.scrollIntoView({ behavior: "smooth" })
                      }
                      className="w-full text-left px-3 py-2 rounded-xl text-sm text-slate-500 hover:text-slate-300 hover:bg-ink-900/[0.04] transition-all flex items-center gap-2"
                    >
                      <Hotel className="w-3 h-3" />
                      Hotels
                    </button>
                  )}
                  {budgetSlices.length > 0 && (
                    <button
                      onClick={() =>
                        document
                          .getElementById("budget-section")
                          ?.scrollIntoView({ behavior: "smooth" })
                      }
                      className="w-full text-left px-3 py-2 rounded-xl text-sm text-slate-500 hover:text-slate-300 hover:bg-ink-900/[0.04] transition-all flex items-center gap-2"
                    >
                      <Wallet className="w-3 h-3" />
                      Budget
                    </button>
                  )}
                  {trip?.packing_list && (
                    <button
                      onClick={() =>
                        document
                          .getElementById("packing-section")
                          ?.scrollIntoView({ behavior: "smooth" })
                      }
                      className="w-full text-left px-3 py-2 rounded-xl text-sm text-slate-500 hover:text-slate-300 hover:bg-ink-900/[0.04] transition-all flex items-center gap-2"
                    >
                      <Luggage className="w-3 h-3" />
                      Packing
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── CENTER: Main content ──────────────────────────────────────── */}
          <div className="flex-1 min-w-0 space-y-8">

            {/* Budget Overview */}
            {budgetSlices.length > 0 && (
              <motion.section
                id="budget-section"
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <Wallet className="w-4 h-4 text-gold-400" />
                  <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">
                    Budget Breakdown
                  </h2>
                  {trip.budget_state?.deviation_pct != null && (
                    <span
                      className={`ml-auto text-xs px-2.5 py-1 rounded-full font-medium border ${
                        Math.abs(trip.budget_state.deviation_pct) < 5
                          ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                          : trip.budget_state.deviation_pct > 0
                          ? "text-coral-400 bg-coral-500/10 border-coral-500/20"
                          : "text-gold-400 bg-gold-500/10 border-gold-500/20"
                      }`}
                    >
                      {trip.budget_state.deviation_pct > 0 ? "+" : ""}
                      {trip.budget_state.deviation_pct.toFixed(1)}% vs budget
                    </span>
                  )}
                </div>
                <div className="glass-card p-6">
                  <DonutChart
                    slices={budgetSlices}
                    currency={trip.budget_state?.currency ?? trip.budget_currency}
                  />
                </div>
              </motion.section>
            )}

            {/* Itinerary Day Sections */}
            {dayNumbers.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Calendar className="w-4 h-4 text-electric-400" />
                  <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">
                    Itinerary
                  </h2>
                  {trip.status === "planned" && (
                    <button
                      onClick={handleGenerate}
                      disabled={generating}
                      className="ml-auto text-xs text-slate-500 hover:text-electric-400 transition-colors"
                    >
                      Regenerate
                    </button>
                  )}
                </div>

                <div className="space-y-4">
                  {dayNumbers.map((day, idx) => {
                    const dayItems = [...(itemsByDay[day] ?? [])].sort(
                      (a, b) => a.sort_order - b.sort_order,
                    );
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
                        className="glass-card overflow-hidden"
                      >
                        {/* Day header */}
                        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-900/8">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-xl bg-electric-500/15 border border-electric-500/30 flex items-center justify-center">
                              <span className="text-xs font-bold text-electric-400">{day}</span>
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-slate-200">Day {day}</p>
                              {dayItems[0]?.item_date && (
                                <p className="text-xs text-slate-500">
                                  {new Date(
                                    dayItems[0].item_date + "T00:00:00",
                                  ).toLocaleDateString("en-US", {
                                    weekday: "short",
                                    month: "short",
                                    day: "numeric",
                                  })}
                                </p>
                              )}
                            </div>
                          </div>

                          {dayWeather && (
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                              <WeatherIcon
                                code={dayWeather.condition_code}
                                adverse={dayWeather.is_adverse}
                              />
                              <span>
                                {Math.round(dayWeather.temp_min_c)}–
                                {Math.round(dayWeather.temp_max_c)}°C
                              </span>
                            </div>
                          )}
                        </div>

                        {/* Activity timeline */}
                        <div className="px-5 py-4 space-y-0">
                          {dayItems.map((item, itemIdx) => {
                            const typeInfo =
                              ITEM_ICONS[item.item_type] ?? ITEM_ICONS.activity;
                            const ItemIcon = typeInfo.icon as React.ComponentType<{ className?: string; strokeWidth?: number }>;
                            const isLast = itemIdx === dayItems.length - 1;

                            return (
                              <div key={item.id}>
                                <div className="flex gap-4 py-3">
                                  {/* Timeline line + icon */}
                                  <div className="flex flex-col items-center shrink-0">
                                    <div
                                      className={`w-7 h-7 rounded-lg flex items-center justify-center border ${typeInfo.color} bg-current/10`}
                                      style={{ borderColor: "currentColor", opacity: 1 }}
                                    >
                                      <ItemIcon
                                        className={`w-3.5 h-3.5 ${typeInfo.color}`}
                                        strokeWidth={2}
                                      />
                                    </div>
                                    {!isLast && (
                                      <div className="w-px flex-1 bg-ink-900/[0.05] mt-1.5 min-h-[16px]" />
                                    )}
                                  </div>

                                  {/* Content */}
                                  <div className="flex-1 min-w-0 pb-1">
                                    <div className="flex items-start justify-between gap-2">
                                      <div className="min-w-0">
                                        {item.start_time && (
                                          <p className="text-[10px] text-slate-600 font-mono mb-0.5">
                                            {item.start_time}
                                          </p>
                                        )}
                                        <p className="text-sm font-medium text-slate-200 leading-snug">
                                          {item.title}
                                        </p>
                                        {item.address && (
                                          <p className="text-xs text-slate-500 truncate mt-0.5 flex items-center gap-1">
                                            <MapPin className="w-2.5 h-2.5 shrink-0" />
                                            {item.address}
                                          </p>
                                        )}
                                        {item.description && (
                                          <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                                            {item.description}
                                          </p>
                                        )}
                                      </div>

                                      <div className="flex flex-col items-end gap-1.5 shrink-0">
                                        {item.est_cost != null && (
                                          <span className="text-xs font-semibold text-gold-400 tabular-nums whitespace-nowrap">
                                            {item.est_cost_currency ?? ""} {item.est_cost}
                                          </span>
                                        )}
                                        <button
                                          onClick={() => {
                                            setReplaceTitle("");
                                            setReplaceTarget(
                                              replaceTarget === item.id ? null : item.id,
                                            );
                                          }}
                                          className="text-[10px] text-slate-600 hover:text-electric-400 transition-colors px-2 py-0.5 rounded-lg hover:bg-electric-500/10"
                                        >
                                          Replace
                                        </button>
                                      </div>
                                    </div>

                                    {/* Replace form */}
                                    <AnimatePresence>
                                      {replaceTarget === item.id && (
                                        <motion.div
                                          initial={{ opacity: 0, height: 0 }}
                                          animate={{ opacity: 1, height: "auto" }}
                                          exit={{ opacity: 0, height: 0 }}
                                          className="mt-2 flex gap-2 items-center overflow-hidden"
                                        >
                                          <input
                                            autoFocus
                                            type="text"
                                            value={replaceTitle}
                                            onChange={(e) => setReplaceTitle(e.target.value)}
                                            onKeyDown={(e) => {
                                              if (e.key === "Enter") handleReplace(item.id);
                                              if (e.key === "Escape") setReplaceTarget(null);
                                            }}
                                            placeholder="Replacement activity name…"
                                            disabled={replaceLoading}
                                            className="input-dark text-xs py-2 flex-1"
                                          />
                                          <button
                                            onClick={() => handleReplace(item.id)}
                                            disabled={replaceLoading || !replaceTitle.trim()}
                                            className="text-xs bg-electric-500/15 text-electric-400 border border-electric-500/30 px-3 py-2 rounded-xl hover:bg-electric-500/25 transition-colors disabled:opacity-40 whitespace-nowrap"
                                          >
                                            {replaceLoading ? "…" : "Submit"}
                                          </button>
                                          <button
                                            onClick={() => setReplaceTarget(null)}
                                            className="text-slate-500 hover:text-slate-300 text-xs"
                                          >
                                            <X className="w-4 h-4" />
                                          </button>
                                        </motion.div>
                                      )}
                                    </AnimatePresence>

                                    {/* Conflict warning */}
                                    {item.conflict_warning && (
                                      <div className="mt-2 flex items-start gap-1.5 text-xs text-gold-400 bg-gold-500/8 border border-gold-500/20 rounded-xl px-3 py-2">
                                        <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                                        <span>{item.conflict_warning}</span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        {/* Ask concierge chip */}
                        <div className="px-5 pb-4">
                          <button
                            onClick={() => setChatOpen(true)}
                            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-electric-400 transition-colors py-1.5 px-3 rounded-full border border-ink-900/10 hover:border-electric-500/30 hover:bg-electric-500/8"
                          >
                            <Compass className="w-3 h-3" />
                            Ask Concierge about Day {day} →
                          </button>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Empty itinerary state */}
            {trip.status !== "planning" && trip.status !== "failed" && dayNumbers.length === 0 && (
              <div className="glass-card p-10 text-center">
                <Loader2 className="w-8 h-8 text-electric-400 animate-spin mx-auto mb-3" />
                <p className="text-slate-500 text-sm">
                  {trip.status === "generating"
                    ? "Building your itinerary…"
                    : "No items yet. Items will appear here once the agents finish."}
                </p>
              </div>
            )}

            {/* Hotels Section */}
            {hotels.length > 0 && (
              <motion.section
                id="hotels-section"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4 }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <Hotel className="w-4 h-4 text-coral-400" />
                  <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">
                    Hotels
                  </h2>
                </div>

                <div className="space-y-3">
                  {/* Selected hotel — prominent */}
                  {selectedHotel && (
                    <div className="glass-card p-5 border-electric-500/30 shadow-electric-sm">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-[10px] font-semibold text-electric-400 bg-electric-500/10 border border-electric-500/20 px-2 py-0.5 rounded-full">
                              Selected
                            </span>
                            {selectedHotel.refundable != null && (
                              <span
                                className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${
                                  selectedHotel.refundable
                                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                                    : "text-coral-400 bg-coral-500/10 border-coral-500/20"
                                }`}
                              >
                                {selectedHotel.refundable ? "Refundable" : "Non-refundable"}
                              </span>
                            )}
                          </div>
                          <p className="font-bold text-slate-100 text-base leading-snug">
                            {selectedHotel.name}
                          </p>
                          {selectedHotel.star_rating != null && (
                            <div className="flex items-center gap-1 mt-0.5">
                              {Array.from({ length: 5 }).map((_, i) => (
                                <Star
                                  key={i}
                                  className={`w-3 h-3 ${
                                    i < Math.round(selectedHotel.star_rating!)
                                      ? "text-gold-400 fill-gold-400"
                                      : "text-slate-700"
                                  }`}
                                />
                              ))}
                              <span className="text-xs text-slate-500 ml-1">
                                {selectedHotel.star_rating.toFixed(1)}
                              </span>
                            </div>
                          )}
                          {selectedHotel.address && (
                            <p className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                              <MapPin className="w-3 h-3 shrink-0" />
                              {selectedHotel.address}
                            </p>
                          )}
                          {selectedHotel.meal_plan && (
                            <span className="inline-block mt-2 text-[10px] text-slate-500 bg-ink-900/[0.04] border border-ink-900/10 px-2 py-0.5 rounded-full">
                              {selectedHotel.meal_plan}
                            </span>
                          )}
                        </div>

                        {(selectedHotel.price_per_night != null ||
                          selectedHotel.price_total != null) && (
                          <div className="text-right shrink-0">
                            {selectedHotel.price_per_night != null && (
                              <p className="text-lg font-bold text-slate-100 tabular-nums">
                                {selectedHotel.price_currency ?? ""}{" "}
                                {selectedHotel.price_per_night.toLocaleString()}
                                <span className="text-xs font-normal text-slate-500">/night</span>
                              </p>
                            )}
                            {selectedHotel.price_total != null && (
                              <p className="text-xs text-slate-500 tabular-nums mt-0.5">
                                {selectedHotel.price_currency ?? ""}{" "}
                                {selectedHotel.price_total.toLocaleString()} total
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Other hotel candidates */}
                  {otherHotels.map((hotel) => (
                    <div key={hotel.id} className="glass-card p-4 opacity-80 hover:opacity-100 transition-opacity">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <p className="font-medium text-slate-300 text-sm">{hotel.name}</p>
                          </div>
                          {hotel.star_rating != null && (
                            <div className="flex items-center gap-0.5 mt-0.5">
                              {Array.from({ length: 5 }).map((_, i) => (
                                <Star
                                  key={i}
                                  className={`w-2.5 h-2.5 ${
                                    i < Math.round(hotel.star_rating!)
                                      ? "text-gold-400 fill-gold-400"
                                      : "text-slate-700"
                                  }`}
                                />
                              ))}
                            </div>
                          )}
                          {hotel.address && (
                            <p className="text-xs text-slate-600 truncate mt-0.5">{hotel.address}</p>
                          )}
                          <div className="flex items-center gap-2 mt-1.5">
                            {hotel.meal_plan && (
                              <span className="text-[10px] text-slate-600 bg-ink-900/[0.03] border border-ink-900/8 px-1.5 py-0.5 rounded-full">
                                {hotel.meal_plan}
                              </span>
                            )}
                            {hotel.refundable != null && (
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                                  hotel.refundable
                                    ? "text-emerald-500 bg-emerald-500/8"
                                    : "text-coral-500 bg-coral-500/8"
                                }`}
                              >
                                {hotel.refundable ? "Refundable" : "Non-refundable"}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="text-right shrink-0 flex flex-col items-end gap-2">
                          <div>
                            {hotel.price_per_night != null && (
                              <p className="text-sm font-semibold text-slate-300 tabular-nums">
                                {hotel.price_currency ?? ""} {hotel.price_per_night.toLocaleString()}
                                <span className="text-[10px] font-normal text-slate-600">/night</span>
                              </p>
                            )}
                            {hotel.price_total != null && (
                              <p className="text-[10px] text-slate-600 tabular-nums">
                                {hotel.price_currency ?? ""} {hotel.price_total.toLocaleString()} total
                              </p>
                            )}
                          </div>
                          <motion.button
                            whileTap={{ scale: 0.96 }}
                            onClick={async () => {
                              const updated = await api.selectHotel(tripId, hotel.id);
                              queryClient.setQueryData(["hotels", tripId], updated);
                            }}
                            className="text-[10px] font-semibold px-2.5 py-1 rounded-lg bg-electric-500/10 text-electric-400 border border-electric-500/20 hover:bg-electric-500/20 transition-colors whitespace-nowrap"
                          >
                            Set as hotel
                          </motion.button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.section>
            )}

            {/* Packing List */}
            <PackingListPanel packingList={trip.packing_list} />

          </div>

          {/* ── RIGHT SIDEBAR ─────────────────────────────────────────────── */}
          <div className="hidden xl:block w-[280px] shrink-0">
            <div className="sticky top-24 space-y-4">

              {/* Map */}
              {trip.latitude != null && trip.longitude != null && pinnedItems.length > 0 && (
                <div className="glass-card overflow-hidden">
                  <div className="flex items-center gap-2 px-4 pt-4 pb-2">
                    <MapPin className="w-3.5 h-3.5 text-electric-400" />
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
                      Map
                    </p>
                  </div>
                  <TripMap
                    items={pinnedItems}
                    centerLat={trip.latitude}
                    centerLng={trip.longitude}
                  />
                </div>
              )}

              {/* Agent Activity collapsible */}
              {trip.agent_messages && trip.agent_messages.length > 0 && (
                <AgentActivityPanel messages={trip.agent_messages} />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Floating Concierge Button ──────────────────────────────────────── */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
        {/* Chat panel */}
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="w-[360px] max-w-[calc(100vw-2rem)] glass-card overflow-hidden flex flex-col"
              style={{ height: "50vh", maxHeight: "480px" }}
            >
              {/* Chat header */}
              <div className="flex items-center gap-3 px-4 py-3 border-b border-ink-900/10 shrink-0">
                <div className="w-7 h-7 rounded-xl bg-electric-gradient flex items-center justify-center shadow-electric-sm">
                  <Compass className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-200">AI Concierge</p>
                  <p className="text-[10px] text-slate-500">Powered by TravelOS agents</p>
                </div>
                <button
                  onClick={() => setChatOpen(false)}
                  className="text-slate-500 hover:text-slate-300 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
                {chatMessages.length === 0 && (
                  <div className="text-center py-8">
                    <p className="text-xs text-slate-600 leading-relaxed">
                      Ask me anything about your trip — restaurants, packing tips, local advice…
                    </p>
                    <div className="flex flex-wrap gap-1.5 justify-center mt-3">
                      {[
                        "Best restaurants nearby?",
                        "What should I pack?",
                        "Local transport tips",
                      ].map((q) => (
                        <button
                          key={q}
                          onClick={() => {
                            setChatMessages((prev) => [
                              ...prev,
                              { role: "user", text: q },
                            ]);
                            setChatLoading(true);
                            sendMessage(q).finally(() => setChatLoading(false));
                          }}
                          className="text-[10px] text-electric-400 bg-electric-500/10 border border-electric-500/20 px-2.5 py-1 rounded-full hover:bg-electric-500/20 transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {chatMessages.map((msg, i) => (
                  <div key={i}>
                    <div
                      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] text-xs px-3.5 py-2.5 rounded-2xl leading-relaxed ${
                          msg.role === "user"
                            ? "bg-electric-gradient text-white rounded-br-sm shadow-electric-sm"
                            : "glass-light text-slate-300 rounded-bl-sm border border-ink-900/10"
                        }`}
                      >
                        {msg.text}
                      </div>
                    </div>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5 ml-1">
                        {msg.sources.slice(0, 4).map((s, j) => (
                          <span
                            key={j}
                            className="text-[10px] bg-ink-900/[0.04] text-slate-500 px-2 py-0.5 rounded-full border border-ink-900/10"
                          >
                            {s.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {chatLoading && (
                  <div className="flex gap-1.5 items-center px-3 py-2">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="w-1.5 h-1.5 bg-electric-400 rounded-full animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <form
                onSubmit={handleChatSubmit}
                className="flex gap-2 px-3 py-3 border-t border-ink-900/10 shrink-0"
              >
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={chatLoading}
                  placeholder="Ask anything…"
                  className="input-dark text-xs py-2 flex-1"
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatInput.trim()}
                  className="w-9 h-9 rounded-xl bg-electric-gradient text-white flex items-center justify-center hover:opacity-90 disabled:opacity-40 transition-opacity shadow-electric-sm shrink-0"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>

        {/* FAB button */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setChatOpen((v) => !v)}
          className={`flex items-center gap-2 px-5 py-3 rounded-2xl font-semibold text-sm text-white shadow-lg transition-all ${
            chatOpen
              ? "bg-space-700 border border-ink-900/15"
              : "bg-electric-gradient shadow-electric"
          } ${pendingApprovals.length > 0 ? "animate-pulse-glow" : ""}`}
        >
          <Compass className="w-4 h-4" />
          {chatOpen ? "Close" : "Ask AI"}
          {!chatOpen && pendingApprovals.length > 0 && (
            <span className="w-2 h-2 rounded-full bg-coral-400" />
          )}
        </motion.button>
      </div>

      {/* ── Edit Trip Modal ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {editOpen && trip && (
          <EditTripModal
            trip={trip}
            onClose={() => setEditOpen(false)}
            onSave={handleEditSave}
          />
        )}
      </AnimatePresence>

      {/* ── Delete Confirmation Modal ────────────────────────────────────── */}
      <AnimatePresence>
        {deleteConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/40 backdrop-blur-sm"
            onClick={() => setDeleteConfirm(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 8 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 8 }}
              transition={{ type: "spring", damping: 28, stiffness: 340 }}
              className="glass-card p-6 w-full max-w-sm"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3 mb-5">
                <div className="p-2 rounded-xl bg-coral-500/10 border border-coral-500/20 shrink-0">
                  <Trash2 className="w-4 h-4 text-coral-400" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-slate-100 mb-1">Delete trip?</h2>
                  <p className="text-sm text-slate-400">
                    This will permanently remove{" "}
                    <span className="text-slate-200">{trip?.title}</span> and all its itinerary
                    data. This cannot be undone.
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteConfirm(false)}
                  className="flex-1 py-2.5 rounded-xl text-sm text-slate-400 border border-ink-900/10 hover:bg-ink-900/[0.04] transition-colors"
                >
                  Cancel
                </button>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={handleDelete}
                  disabled={deleting}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-coral-500 text-white hover:bg-coral-600 transition-colors disabled:opacity-50"
                >
                  {deleting ? "Deleting…" : "Delete"}
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Agent name formatter ──────────────────────────────────────────────────────

const AGENT_DISPLAY: Record<string, { label: string; color: string; emoji: string }> = {
  travel_style:     { label: "Travel Style",     color: "text-electric-400",  emoji: "🧬" },
  itinerary_planner:{ label: "Itinerary Planner",color: "text-gold-400",      emoji: "🗺" },
  hotel_agent:      { label: "Hotel Agent",       color: "text-coral-400",     emoji: "🏨" },
  budget_optimizer: { label: "Budget Optimizer",  color: "text-emerald-400",   emoji: "💰" },
  events_agent:     { label: "Events Agent",      color: "text-purple-400",    emoji: "🎟" },
  packing_list:     { label: "Packing List",      color: "text-teal-400",      emoji: "🧳" },
  supervisor:       { label: "Supervisor",        color: "text-slate-400",     emoji: "🤖" },
  validation:       { label: "Validation",        color: "text-slate-400",     emoji: "✅" },
  conflict_detection:{ label: "Conflict Check",  color: "text-orange-400",    emoji: "⚠️" },
  human:            { label: "Human",             color: "text-slate-300",     emoji: "👤" },
  ai:               { label: "AI",                color: "text-electric-400",  emoji: "⚡" },
};

function agentMeta(role: string) {
  return AGENT_DISPLAY[role] ?? { label: role, color: "text-slate-400", emoji: "🔷" };
}

// ── Agent Activity drawer ──────────────────────────────────────────────────────

function AgentActivityPanel({
  messages,
}: {
  messages: { role: string; content: string }[];
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Group consecutive messages by agent
  type Group = { role: string; msgs: string[] };
  const groups: Group[] = [];
  for (const msg of messages) {
    if (groups.length > 0 && groups[groups.length - 1].role === msg.role) {
      groups[groups.length - 1].msgs.push(msg.content);
    } else {
      groups.push({ role: msg.role, msgs: [msg.content] });
    }
  }

  return (
    <>
      {/* Sidebar teaser card */}
      <div className="glass-card overflow-hidden">
        <button
          onClick={() => setDrawerOpen(true)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-ink-900/[0.03] transition-colors"
        >
          <div className="flex items-center gap-2">
            <ZapIcon className="w-3.5 h-3.5 text-electric-400" />
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
              Agent Log
            </p>
          </div>
          <span className="text-[10px] text-slate-600 bg-ink-900/[0.04] px-2 py-0.5 rounded-full">
            {messages.length} events
          </span>
        </button>

        {/* Last 3 messages preview */}
        <div className="px-4 pb-3 space-y-1 border-t border-ink-900/8 pt-2">
          {messages.slice(-3).map((msg, i) => {
            const meta = agentMeta(msg.role);
            return (
              <p key={i} className="text-[10px] text-slate-600 leading-relaxed truncate">
                <span className={`${meta.color} font-medium`}>{meta.emoji} {meta.label}:</span>{" "}
                {msg.content.slice(0, 60)}{msg.content.length > 60 ? "…" : ""}
              </p>
            );
          })}
          {messages.length > 3 && (
            <button
              onClick={() => setDrawerOpen(true)}
              className="text-[10px] text-electric-400 hover:underline mt-1"
            >
              View all {messages.length} events →
            </button>
          )}
        </div>
      </div>

      {/* Full-height right drawer */}
      <AnimatePresence>
        {drawerOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-ink-900/40 backdrop-blur-sm z-40"
              onClick={() => setDrawerOpen(false)}
            />

            {/* Drawer */}
            <motion.div
              key="drawer"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="fixed top-0 right-0 h-full w-full max-w-[420px] bg-space-900 border-l border-ink-900/10 z-50 flex flex-col shadow-2xl"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-ink-900/10 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-electric-500/15 border border-electric-500/30 flex items-center justify-center">
                    <ZapIcon className="w-4 h-4 text-electric-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-200">Agent Activity Log</p>
                    <p className="text-[10px] text-slate-500">{messages.length} events recorded</p>
                  </div>
                </div>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="text-slate-500 hover:text-slate-300 transition-colors p-1"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Scroll body */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {groups.length === 0 && (
                  <p className="text-xs text-slate-600 text-center py-12">No activity recorded yet.</p>
                )}
                {groups.map((group, gi) => {
                  const meta = agentMeta(group.role);
                  return (
                    <motion.div
                      key={gi}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: gi * 0.03 }}
                      className="flex gap-3"
                    >
                      {/* Timeline dot */}
                      <div className="flex flex-col items-center gap-0 mt-0.5 shrink-0">
                        <div
                          className={`w-6 h-6 rounded-lg border flex items-center justify-center text-[11px] shrink-0 ${meta.color} border-current bg-current/10`}
                        >
                          {meta.emoji}
                        </div>
                        {gi < groups.length - 1 && (
                          <div className="w-px flex-1 bg-ink-900/[0.05] mt-1" />
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0 pb-4">
                        <p className={`text-xs font-semibold mb-1.5 ${meta.color}`}>{meta.label}</p>
                        <div className="space-y-1">
                          {group.msgs.map((text, mi) => (
                            <p key={mi} className="text-[11px] text-slate-400 leading-relaxed">
                              {text}
                            </p>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {/* Footer */}
              <div className="px-5 py-3 border-t border-ink-900/10 shrink-0">
                <p className="text-[10px] text-slate-600 text-center">
                  Powered by TravelOS multi-agent system
                </p>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
