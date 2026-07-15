"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import {
  MapPin,
  Calendar,
  Users,
  Loader2,
  ChevronDown,
  Sparkles,
  ArrowRight,
  Clock,
  Shirt,
  Plug,
  FileText,
  Pill,
  Backpack,
  Package,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ShareTripOut, ItineraryItemOut } from "@/lib/api";
import { ITEM_ICONS } from "@/lib/constants";
import { CoverArt } from "@/components/ui/CoverArt";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { SectionHeader } from "@/components/ui/SectionHeader";

const TONE_TEXT: Record<string, string> = {
  accent: "text-accent",
  warning: "text-warning",
  info: "text-info",
  success: "text-success",
  danger: "text-danger",
  neutral: "text-ink-400",
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

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  Clothing: Shirt,
  Electronics: Plug,
  Documents: FileText,
  Health: Pill,
  Accessories: Backpack,
  "Destination-Specific": MapPin,
};

function PackingCategory({ name, items }: { name: string; items: string[] }) {
  const [open, setOpen] = useState(false);
  const Icon = CATEGORY_ICONS[name] ?? Package;
  return (
    <div className="border border-ink-900/10 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-ink-900/[0.03] transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Icon className="w-4 h-4 text-ink-400" />
          <span className="text-sm font-medium text-ink-900">{name}</span>
          <span className="text-xs text-ink-400 bg-ink-100 px-2 py-0.5 rounded-full">{items.length}</span>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-4 h-4 text-ink-400" />
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
                <div key={i} className="flex items-center gap-2 text-sm text-ink-600">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent/60 shrink-0" />
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
  const cfg = ITEM_ICONS[item.item_type] ?? ITEM_ICONS.free;
  const Icon = cfg.icon;
  const startFmt = formatTime(item.start_time);
  const endFmt = formatTime(item.end_time);

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05, duration: 0.35 }}
      className="flex items-start gap-3 p-4 rounded-xl bg-surface border border-ink-900/10 hover:border-ink-900/20 transition-colors"
    >
      <div className={`mt-0.5 p-2 rounded-lg bg-ink-100 shrink-0 ${TONE_TEXT[cfg.tone]}`}>
        <Icon className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-ink-900 leading-snug truncate">{item.title}</p>
        {item.description && <p className="text-xs text-ink-400 mt-0.5 line-clamp-2">{item.description}</p>}
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5 font-mono">
          {startFmt && (
            <span className="flex items-center gap-1 text-xs text-ink-400">
              <Clock className="w-3 h-3" />
              {startFmt}
              {endFmt ? ` – ${endFmt}` : ""}
            </span>
          )}
          {item.est_cost != null && (
            <span className="text-xs text-ink-400">
              {item.est_cost_currency ?? ""} {item.est_cost.toLocaleString()}
            </span>
          )}
          {item.is_outdoor && <span className="text-xs text-success">Outdoor</span>}
        </div>
      </div>
    </motion.div>
  );
}

// ── Day group ─────────────────────────────────────────────────────────────────

function DayGroup({ dayNum, date, items }: { dayNum: number; date: string; items: ItineraryItemOut[] }) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-medium text-accent bg-accent-tint px-2.5 py-1 rounded-full">Day {dayNum}</span>
          <span className="text-sm text-ink-400">{formatDate(date)}</span>
        </div>
        <div className="flex-1 h-px bg-ink-900/10" />
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

  const {
    data: trip,
    isLoading,
    error,
  } = useQuery<ShareTripOut>({
    queryKey: ["share", token],
    queryFn: () => api.getSharedTrip(token),
    retry: false,
    enabled: !!token,
  });

  // ── Loading ───────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <p className="text-ink-400 text-sm">Loading shared itinerary…</p>
        </div>
      </div>
    );
  }

  // ── Error / expired / not found ───────────────────────────────────────────

  if (error || !trip) {
    const isExpired = error instanceof ApiError && error.status === 410;
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center px-4">
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm">
          <Card className="p-10 text-center">
            <div className="w-14 h-14 rounded-xl bg-danger-tint flex items-center justify-center mx-auto mb-5">
              <MapPin className="w-7 h-7 text-danger" />
            </div>
            <h1 className="font-display text-xl font-medium text-ink-900 mb-2">{isExpired ? "Link Expired" : "Link Not Found"}</h1>
            <p className="text-sm text-ink-400 mb-6">
              {isExpired
                ? "This share link has expired. Ask the trip owner to generate a new one."
                : "This share link doesn't exist or has been removed."}
            </p>
            <Link href="/login" className="inline-flex items-center gap-2 text-sm text-accent hover:text-accent-deep transition-colors">
              Plan your own trip with TravelOS
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </Card>
        </motion.div>
      </div>
    );
  }

  // ── Data ──────────────────────────────────────────────────────────────────

  const nights = Math.max(
    1,
    Math.round((new Date(trip.end_date + "T00:00:00").getTime() - new Date(trip.start_date + "T00:00:00").getTime()) / 86400000),
  );

  // Group itinerary by day
  const byDay = trip.itinerary.reduce<Record<number, { date: string; items: ItineraryItemOut[] }>>((acc, item) => {
    if (!acc[item.day_number]) acc[item.day_number] = { date: item.item_date, items: [] };
    acc[item.day_number].items.push(item);
    return acc;
  }, {});
  const days = Object.keys(byDay)
    .map(Number)
    .sort((a, b) => a - b);

  // Packing list categories
  const packingCategories =
    trip.packing_list?.categories != null ? Object.entries(trip.packing_list.categories as Record<string, string[]>) : [];
  const destSpecific = trip.packing_list?.destination_specific ?? [];

  return (
    <div className="min-h-screen bg-paper">
      {/* ── Hero banner ──────────────────────────────────────────────────────── */}
      <CoverArt city={trip.destination_city} country={trip.destination_country} imageUrl={trip.cover_image_url} height="h-48 sm:h-56">
        <div className="relative h-full px-4 sm:px-6">
          <div className="absolute top-4 right-4 sm:right-6 flex items-center gap-1.5 text-xs text-white/85 bg-black/35 px-3 py-1.5 rounded-full border border-white/15">
            <Sparkles className="w-3 h-3" />
            Shared itinerary
          </div>

          <div className="h-full flex flex-col justify-end pb-5 max-w-3xl mx-auto">
            <div className="flex items-center gap-2 mb-1">
              <MapPin className="w-3.5 h-3.5 text-white/70" />
              <span className="text-white/70 text-xs font-mono uppercase tracking-widest">{trip.destination_country ?? ""}</span>
            </div>
            <h1 className="font-display text-3xl sm:text-4xl font-medium text-white leading-tight">{trip.destination_city}</h1>
          </div>
        </div>
      </CoverArt>

      {/* ── Content ───────────────────────────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Meta pills */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex flex-wrap gap-2 font-mono"
        >
          <div className="flex items-center gap-1.5 text-xs text-ink-600 bg-ink-100 px-3 py-1.5 rounded-full">
            <Calendar className="w-3 h-3" />
            {new Date(trip.start_date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })} –{" "}
            {new Date(trip.end_date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-ink-600 bg-ink-100 px-3 py-1.5 rounded-full">
            <Users className="w-3 h-3" />
            {trip.num_travelers} traveler{trip.num_travelers !== 1 ? "s" : ""}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-ink-600 bg-ink-100 px-3 py-1.5 rounded-full">
            <Calendar className="w-3 h-3" />
            {nights} night{nights !== 1 ? "s" : ""}
          </div>
        </motion.div>

        {/* ── Itinerary ───────────────────────────────────────────────────────── */}
        {days.length > 0 ? (
          <section>
            <SectionHeader eyebrow="Itinerary" />
            <div className="space-y-8">
              {days.map((d) => (
                <DayGroup key={d} dayNum={d} date={byDay[d].date} items={byDay[d].items} />
              ))}
            </div>
          </section>
        ) : (
          <Card className="p-8 text-center">
            <p className="text-ink-400 text-sm">No itinerary items yet.</p>
          </Card>
        )}

        {/* ── Packing list ────────────────────────────────────────────────────── */}
        {(packingCategories.length > 0 || destSpecific.length > 0) && (
          <section>
            <SectionHeader eyebrow="Packing List" />
            <Card padding="sm" className="space-y-2">
              {packingCategories.map(([name, items]) => (
                <PackingCategory key={name} name={name} items={items} />
              ))}
              {destSpecific.length > 0 && <PackingCategory name="Destination-Specific" items={destSpecific} />}
            </Card>
          </section>
        )}

        {/* ── CTA ─────────────────────────────────────────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.4 }}>
          <Card className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-ink-900">Plan your own AI-powered trip</p>
              <p className="text-xs text-ink-400 mt-0.5">TravelOS remembers your style and gets smarter every trip.</p>
            </div>
            <Link href="/login" className="shrink-0">
              <Button size="sm" iconRight={ArrowRight}>
                Get started
              </Button>
            </Link>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
