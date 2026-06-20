"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  Compass, MapPin, Calendar, Users, Loader2,
  Utensils, Bus, Hotel, Coffee, ChevronDown,
  Luggage, Sparkles, ArrowRight, Clock,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ShareTripOut, ItineraryItemOut } from "@/lib/api";

// ── Destination gradient (deterministic hash of city name) ───────────────────

const GRADIENTS = [
  "from-blue-600/70 via-indigo-700/60 to-violet-900/80",
  "from-emerald-600/70 via-teal-700/60 to-cyan-900/80",
  "from-rose-600/70 via-pink-700/60 to-purple-900/80",
  "from-amber-600/70 via-orange-700/60 to-red-900/80",
  "from-sky-600/70 via-blue-700/60 to-indigo-900/80",
  "from-violet-600/70 via-purple-700/60 to-fuchsia-900/80",
];

function destGradient(city: string): string {
  let h = 0;
  for (let i = 0; i < city.length; i++) h = (h * 31 + city.charCodeAt(i)) >>> 0;
  return GRADIENTS[h % GRADIENTS.length];
}

// ── Item type config ──────────────────────────────────────────────────────────

const ITEM_TYPE_CONFIG: Record<string, { icon: LucideIcon; color: string; label: string }> = {
  activity: { icon: Compass, color: "text-electric-400", label: "Activity" },
  meal: { icon: Utensils, color: "text-gold", label: "Meal" },
  transport: { icon: Bus, color: "text-slate-400", label: "Transport" },
  lodging: { icon: Hotel, color: "text-purple-400", label: "Lodging" },
  free: { icon: Coffee, color: "text-emerald-400", label: "Free time" },
};

function formatTime(t: string | null): string | null {
  if (!t) return null;
  const [h, m] = t.split(":");
  const hour = parseInt(h, 10);
  const ampm = hour >= 12 ? "PM" : "AM";
  const h12 = hour % 12 || 12;
  return `${h12}:${m} ${ampm}`;
}

function formatDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

// ── Packing list collapsible ──────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, string> = {
  Clothing: "👕",
  Electronics: "🔌",
  Documents: "📄",
  Health: "💊",
  Accessories: "🎒",
  "Destination-Specific": "📍",
};

function PackingCategory({ name, items }: { name: string; items: string[] }) {
  const [open, setOpen] = useState(false);
  const icon = CATEGORY_ICONS[name] ?? "📦";
  return (
    <div className="border border-white/8 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-base">{icon}</span>
          <span className="text-sm font-medium text-white">{name}</span>
          <span className="text-xs text-slate-500 bg-white/5 px-2 py-0.5 rounded-full">
            {items.length}
          </span>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-4 h-4 text-slate-500" />
        </motion.div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-3 pt-1 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {items.map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-slate-400">
                  <div className="w-1.5 h-1.5 rounded-full bg-electric-500/60 shrink-0" />
                  {item}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Itinerary item card ───────────────────────────────────────────────────────

function ItineraryCard({ item, index }: { item: ItineraryItemOut; index: number }) {
  const cfg = ITEM_TYPE_CONFIG[item.item_type] ?? ITEM_TYPE_CONFIG.free;
  const Icon = cfg.icon;
  const startFmt = formatTime(item.start_time);
  const endFmt = formatTime(item.end_time);

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.35 }}
      className="flex items-start gap-3 p-4 rounded-xl bg-white/4 border border-white/6 hover:bg-white/6 hover:border-white/10 transition-all"
    >
      <div className={`mt-0.5 p-2 rounded-lg bg-black/30 shrink-0 ${cfg.color}`}>
        <Icon className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white leading-snug truncate">{item.title}</p>
        {item.description && (
          <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{item.description}</p>
        )}
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
          {startFmt && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Clock className="w-3 h-3" />
              {startFmt}
              {endFmt ? ` – ${endFmt}` : ""}
            </span>
          )}
          {item.est_cost != null && (
            <span className="text-xs text-slate-500">
              {item.est_cost_currency ?? ""} {item.est_cost.toLocaleString()}
            </span>
          )}
          {item.is_outdoor && (
            <span className="text-xs text-emerald-500/80">Outdoor</span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// ── Day group ─────────────────────────────────────────────────────────────────

function DayGroup({ dayNum, date, items }: { dayNum: number; date: string; items: ItineraryItemOut[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-electric-400 bg-electric-500/10 border border-electric-500/20 px-2.5 py-1 rounded-full">
            Day {dayNum}
          </span>
          <span className="text-sm text-slate-500">{formatDate(date)}</span>
        </div>
        <div className="flex-1 h-px bg-white/6" />
      </div>
      <div className="space-y-2">
        {items.map((item, i) => (
          <ItineraryCard key={item.id} item={item} index={i} />
        ))}
      </div>
    </motion.div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SharePage() {
  const { token } = useParams<{ token: string }>();

  const { data: trip, isLoading, error } = useQuery<ShareTripOut>({
    queryKey: ["share", token],
    queryFn: () => api.getSharedTrip(token),
    retry: false,
    enabled: !!token,
  });

  // ── Loading ───────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="min-h-screen bg-space-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-electric-400 animate-spin" />
          <p className="text-slate-500 text-sm">Loading shared itinerary…</p>
        </div>
      </div>
    );
  }

  // ── Error / expired / not found ───────────────────────────────────────────

  if (error || !trip) {
    const isExpired = error instanceof ApiError && error.status === 410;
    return (
      <div className="min-h-screen bg-space-900 flex items-center justify-center px-4">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-10 max-w-sm w-full text-center"
        >
          <div className="w-14 h-14 rounded-2xl bg-coral/10 flex items-center justify-center mx-auto mb-5">
            <MapPin className="w-7 h-7 text-coral" />
          </div>
          <h1 className="text-xl font-bold text-white mb-2">
            {isExpired ? "Link Expired" : "Link Not Found"}
          </h1>
          <p className="text-sm text-slate-500 mb-6">
            {isExpired
              ? "This share link has expired. Ask the trip owner to generate a new one."
              : "This share link doesn't exist or has been removed."}
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-sm text-electric-400 hover:text-electric-300 transition-colors"
          >
            Plan your own trip with TravelOS
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </motion.div>
      </div>
    );
  }

  // ── Data ──────────────────────────────────────────────────────────────────

  const gradient = destGradient(trip.destination_city);
  const nights = Math.max(
    1,
    Math.round(
      (new Date(trip.end_date + "T00:00:00").getTime() -
        new Date(trip.start_date + "T00:00:00").getTime()) /
        86400000
    )
  );

  // Group itinerary by day
  const byDay = trip.itinerary.reduce<Record<number, { date: string; items: ItineraryItemOut[] }>>(
    (acc, item) => {
      if (!acc[item.day_number]) acc[item.day_number] = { date: item.item_date, items: [] };
      acc[item.day_number].items.push(item);
      return acc;
    },
    {}
  );
  const days = Object.keys(byDay)
    .map(Number)
    .sort((a, b) => a - b);

  // Packing list categories
  const packingCategories =
    trip.packing_list?.categories != null
      ? Object.entries(trip.packing_list.categories as Record<string, string[]>)
      : [];
  const destSpecific = trip.packing_list?.destination_specific ?? [];

  return (
    <div className="min-h-screen bg-space-900">
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-72 bg-electric-500/4 rounded-full blur-3xl" />
        <div className="absolute bottom-32 right-1/4 w-64 h-48 bg-purple-600/4 rounded-full blur-3xl" />
      </div>

      {/* ── Hero banner ──────────────────────────────────────────────────────── */}
      <div
        className={`relative h-48 sm:h-56 overflow-hidden ${!trip.cover_image_url ? `bg-gradient-to-br ${gradient}` : "bg-space-900"}`}
        style={
          trip.cover_image_url
            ? { backgroundImage: `url(${trip.cover_image_url})`, backgroundSize: "cover", backgroundPosition: "center" }
            : undefined
        }
      >
        {!trip.cover_image_url && (
          <div
            className="absolute inset-0 opacity-15"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            }}
          />
        )}
        <div className={`absolute inset-0 ${trip.cover_image_url ? "bg-gradient-to-t from-space-900/90 via-black/40 to-black/20" : "bg-gradient-to-t from-space-900/80 via-transparent to-transparent"}`} />

        {/* Shared badge */}
        <div className="absolute top-4 right-4 flex items-center gap-1.5 text-xs text-white/70 bg-black/30 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/10">
          <Sparkles className="w-3 h-3" />
          Shared itinerary
        </div>

        <div className="relative z-10 h-full flex flex-col justify-end px-4 sm:px-6 pb-5 max-w-3xl mx-auto">
          <div className="flex items-center gap-2 mb-1">
            <MapPin className="w-3.5 h-3.5 text-white/60" />
            <span className="text-white/60 text-xs font-medium uppercase tracking-widest">
              {trip.destination_country ?? ""}
            </span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-white leading-tight">
            {trip.destination_city}
          </h1>
        </div>
      </div>

      {/* ── Content ───────────────────────────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Meta pills */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex flex-wrap gap-2"
        >
          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-white/6 border border-white/8 px-3 py-1.5 rounded-full">
            <Calendar className="w-3 h-3 text-electric-400" />
            {new Date(trip.start_date + "T00:00:00").toLocaleDateString("en-US", {
              month: "short", day: "numeric",
            })}{" "}–{" "}
            {new Date(trip.end_date + "T00:00:00").toLocaleDateString("en-US", {
              month: "short", day: "numeric", year: "numeric",
            })}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-white/6 border border-white/8 px-3 py-1.5 rounded-full">
            <Users className="w-3 h-3 text-gold" />
            {trip.num_travelers} traveler{trip.num_travelers !== 1 ? "s" : ""}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-white/6 border border-white/8 px-3 py-1.5 rounded-full">
            <Calendar className="w-3 h-3 text-emerald-400" />
            {nights} night{nights !== 1 ? "s" : ""}
          </div>
        </motion.div>

        {/* ── Itinerary ───────────────────────────────────────────────────────── */}
        {days.length > 0 ? (
          <section>
            <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
              <Compass className="w-4 h-4 text-electric-400" />
              Itinerary
            </h2>
            <div className="space-y-8">
              {days.map((d) => (
                <DayGroup
                  key={d}
                  dayNum={d}
                  date={byDay[d].date}
                  items={byDay[d].items}
                />
              ))}
            </div>
          </section>
        ) : (
          <div className="glass-card p-8 text-center">
            <p className="text-slate-500 text-sm">No itinerary items yet.</p>
          </div>
        )}

        {/* ── Packing list ────────────────────────────────────────────────────── */}
        {(packingCategories.length > 0 || destSpecific.length > 0) && (
          <section>
            <h2 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
              <Luggage className="w-4 h-4 text-gold" />
              Packing List
            </h2>
            <div className="glass-card p-4 space-y-2">
              {packingCategories.map(([name, items]) => (
                <PackingCategory key={name} name={name} items={items} />
              ))}
              {destSpecific.length > 0 && (
                <PackingCategory name="Destination-Specific" items={destSpecific} />
              )}
            </div>
          </section>
        )}

        {/* ── CTA ─────────────────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.4 }}
          className="glass-card p-6 flex items-center justify-between gap-4"
        >
          <div>
            <p className="text-sm font-semibold text-white">
              Plan your own AI-powered trip
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              TravelOS remembers your style and gets smarter every trip.
            </p>
          </div>
          <Link
            href="/login"
            className="shrink-0 flex items-center gap-1.5 text-xs font-semibold text-white bg-electric-gradient px-4 py-2 rounded-full hover:opacity-90 transition-opacity shadow-electric"
          >
            Get started
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </motion.div>
      </div>
    </div>
  );
}
