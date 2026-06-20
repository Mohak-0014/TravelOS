"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  MapPin, Calendar, Users, DollarSign, Sparkles, Clock,
  CheckCircle2, AlertCircle, Loader2, ArrowRight, Globe2, Trash2,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { TripOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import NavBar from "@/components/ui/NavBar";

// ── Status config ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: typeof CheckCircle2 }> = {
  planning:          { label: "Planning",    color: "text-gold-500 bg-gold-400/15 border border-gold-400/30",       icon: Clock },
  generating:        { label: "Generating…", color: "text-electric-600 bg-electric-500/12 border border-electric-500/25", icon: Loader2 },
  awaiting_approval: { label: "Your Call",   color: "text-coral-600 bg-coral-500/12 border border-coral-500/25",    icon: AlertCircle },
  planned:           { label: "Ready",       color: "text-emerald-600 bg-emerald-400/15 border border-emerald-400/30", icon: CheckCircle2 },
  completed:         { label: "Completed",   color: "text-slate-500 bg-slate-800 border border-slate-700/50",       icon: CheckCircle2 },
};

// ── Destination gradient (sunny travel palette) ───────────────────────────────

const DEST_GRADIENTS = [
  "from-sky-400 via-cyan-500 to-blue-600",
  "from-amber-400 via-orange-500 to-rose-500",
  "from-emerald-400 via-teal-500 to-cyan-600",
  "from-rose-400 via-pink-500 to-fuchsia-600",
  "from-indigo-400 via-blue-500 to-sky-600",
  "from-orange-400 via-amber-500 to-yellow-500",
];

function destGradient(city: string) {
  let hash = 0;
  for (let i = 0; i < city.length; i++) hash = city.charCodeAt(i) + ((hash << 5) - hash);
  return DEST_GRADIENTS[Math.abs(hash) % DEST_GRADIENTS.length];
}

// ── Trip Card ─────────────────────────────────────────────────────────────────

function TripCard({ trip, index, onDelete }: { trip: TripOut; index: number; onDelete: (id: string) => void }) {
  const nights = Math.max(
    1,
    Math.ceil((new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) / 86400000)
  );
  const cfg = STATUS_CONFIG[trip.status] ?? STATUS_CONFIG.planning;
  const Icon = cfg.icon;
  const gradient = destGradient(trip.destination_city);
  const daysUntil = Math.ceil((new Date(trip.start_date).getTime() - Date.now()) / 86400000);
  const isUpcoming = daysUntil > 0;

  return (
    <motion.div
      className="relative group/card"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
    >
      <Link href={`/trips/${trip.id}`} className="block">
        <div className="glass-card overflow-hidden cursor-pointer transition-all duration-300 hover:border-coral-500/30 hover:shadow-card-hover">
          {/* Destination banner — real photo or gradient fallback */}
          <div
            className={`relative h-24 bg-gradient-to-br ${gradient} flex items-end p-4`}
            style={trip.cover_image_url ? {
              backgroundImage: `url(${trip.cover_image_url})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
            } : undefined}
          >
            {/* boarding-pass dotted route flourish on gradient banners */}
            {!trip.cover_image_url && (
              <div className="absolute top-3 left-4 right-4 flex items-center gap-2 opacity-70">
                <span className="w-1.5 h-1.5 rounded-full bg-white" />
                <span className="flex-1 route-dash h-px opacity-80" />
                <Sparkles className="w-3 h-3 text-white/90" />
                <span className="flex-1 route-dash h-px opacity-80" />
                <span className="w-1.5 h-1.5 rounded-full bg-white" />
              </div>
            )}
            {trip.cover_image_url && <div className="absolute inset-0 bg-ink-900/35" />}
            <div className="relative z-10 flex items-end justify-between w-full">
              <div>
                <p className="text-white/80 text-xs font-medium uppercase tracking-widest mb-0.5">
                  {isUpcoming ? `${daysUntil}d away` : trip.destination_country ?? ""}
                </p>
                <h2 className="text-white font-display font-semibold text-xl leading-tight drop-shadow">{trip.destination_city}</h2>
              </div>
              {trip.status === "awaiting_approval" && (
                <div className="flex items-center gap-1 bg-coral-500 text-white text-xs font-bold px-2.5 py-1 rounded-full animate-pulse">
                  <AlertCircle className="w-3 h-3" />
                  Review
                </div>
              )}
            </div>
          </div>

          {/* Card body */}
          <div className="p-4">
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-slate-100 font-semibold text-sm leading-snug flex-1 mr-2">{trip.title}</h3>
              <span className={`status-badge ${cfg.color} shrink-0`}>
                <Icon className={`w-3 h-3 ${trip.status === "generating" ? "animate-spin" : ""}`} />
                {cfg.label}
              </span>
            </div>

            <div className="flex flex-wrap gap-3 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-500" />
                {new Date(trip.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                {" – "}
                {new Date(trip.end_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3 text-slate-500" />
                {nights} nights
              </span>
              {trip.num_travelers > 1 && (
                <span className="flex items-center gap-1">
                  <Users className="w-3 h-3 text-slate-500" />
                  {trip.num_travelers}
                </span>
              )}
              {trip.budget_total && (
                <span className="flex items-center gap-1">
                  <DollarSign className="w-3 h-3 text-slate-500" />
                  {trip.budget_currency} {trip.budget_total.toLocaleString()}
                </span>
              )}
            </div>
          </div>
        </div>
      </Link>

      {/* Delete button — visible on card hover */}
      <button
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(trip.id); }}
        title="Delete trip"
        className="absolute top-2 right-2 z-10 p-1.5 rounded-lg bg-white/85 backdrop-blur-sm text-slate-500 opacity-0 group-hover/card:opacity-100 hover:text-coral-600 hover:bg-coral-500/15 transition-all duration-200 shadow-soft"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className="text-center py-20"
    >
      <div className="inline-flex w-20 h-20 rounded-3xl bg-electric-gradient items-center justify-center shadow-electric mb-6 animate-float-slow">
        <Globe2 className="w-10 h-10 text-white" />
      </div>
      <h3 className="font-display text-3xl font-semibold text-slate-100 mb-2">Where to next?</h3>
      <p className="text-slate-400 mb-8 max-w-xs mx-auto leading-relaxed">
        Tell TravelOS where you want to go. It handles the rest — and gets smarter every trip.
      </p>
      <Link href="/trips/new">
        <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.98 }} className="btn-primary flex items-center gap-2 mx-auto">
          <Sparkles className="w-4 h-4" />
          Plan my first trip
          <ArrowRight className="w-4 h-4" />
        </motion.button>
      </Link>
    </motion.div>
  );
}

// ── "Your World" panel (hand-built SVG globe + pins) ──────────────────────────

function WorldPanel({ trips }: { trips: TripOut[] }) {
  const dests = trips
    .filter((t) => t.status === "planned" || t.status === "completed")
    .slice(0, 8);

  return (
    <div className="glass-card p-6">
      <div className="flex items-center gap-2 mb-1">
        <Globe2 className="w-4 h-4 text-coral-500" />
        <span className="text-sm font-semibold text-slate-200">Your World</span>
      </div>
      <p className="text-xs text-slate-500 mb-4">{trips.length} trip{trips.length !== 1 ? "s" : ""} planned</p>

      <motion.div className="relative mx-auto w-[210px] h-[210px] my-2" animate={{ y: [0, -6, 0] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}>
        {/* globe */}
        <div className="absolute inset-0 rounded-full shadow-soft bg-[radial-gradient(circle_at_34%_30%,#dcefff_0%,#8ec9ef_48%,#3a92c9_100%)]" />
        {/* lat/long lines + flight arcs */}
        <svg viewBox="0 0 210 210" className="absolute inset-0 w-full h-full">
          <defs>
            <clipPath id="globeClip"><circle cx="105" cy="105" r="104" /></clipPath>
          </defs>
          <g clipPath="url(#globeClip)" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1">
            <ellipse cx="105" cy="105" rx="104" ry="40" />
            <ellipse cx="105" cy="105" rx="104" ry="72" />
            <ellipse cx="105" cy="105" rx="40" ry="104" />
            <ellipse cx="105" cy="105" rx="72" ry="104" />
            <line x1="1" y1="105" x2="209" y2="105" />
          </g>
          {/* dotted flight arc */}
          <path d="M40 150 Q 105 30 175 95" fill="none" stroke="#ff6b5c" strokeWidth="2" strokeDasharray="2 7" strokeLinecap="round" opacity="0.9" />
          <circle cx="40" cy="150" r="4" fill="#ff6b5c" />
          <circle cx="175" cy="95" r="4" fill="#f5a623" />
        </svg>
        {/* destination pins */}
        {dests.map((t, i) => {
          const ang = (i / Math.max(1, dests.length)) * Math.PI * 2 - Math.PI / 2;
          const rad = 66;
          const x = 105 + Math.cos(ang) * rad;
          const y = 105 + Math.sin(ang) * rad;
          return (
            <div key={t.id} className="absolute -translate-x-1/2 -translate-y-full" style={{ left: x, top: y }} title={t.destination_city}>
              <MapPin className="w-4 h-4 text-coral-600 drop-shadow-[0_2px_3px_rgba(20,34,61,0.3)]" fill="#ff6b5c" />
            </div>
          );
        })}
      </motion.div>

      {dests.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-4 justify-center">
          {dests.map((t) => (
            <span key={t.id} className="text-[11px] px-2 py-0.5 rounded-full bg-space-800 border border-ink-900/8 text-slate-400">
              {t.destination_city}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TripsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, user, _hasHydrated } = useAuthStore();
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (_hasHydrated && !token) router.replace("/login");
  }, [_hasHydrated, token, router]);

  const { data: trips, isLoading } = useQuery<TripOut[]>({
    queryKey: ["trips"],
    queryFn: () => api.get<TripOut[]>("/api/v1/trips"),
    enabled: !!token,
    refetchInterval: 8000,
  });

  async function handleDeleteConfirm() {
    if (!deleteConfirmId || deleting) return;
    setDeleting(true);
    try {
      await api.deleteTrip(deleteConfirmId);
      queryClient.invalidateQueries({ queryKey: ["trips"] });
    } finally {
      setDeleting(false);
      setDeleteConfirmId(null);
    }
  }

  if (!_hasHydrated) return null;

  const upcoming = trips?.filter((t) => new Date(t.start_date) >= new Date()) ?? [];
  const past = trips?.filter((t) => new Date(t.start_date) < new Date()) ?? [];

  return (
    <div className="relative min-h-screen bg-space-900">
      <NavBar />

      {/* Soft sky wash at top */}
      <div className="absolute top-0 left-0 right-0 h-96 pointer-events-none overflow-hidden">
        <div className="absolute inset-0 bg-sky-gradient opacity-60" />
        <div className="absolute top-10 left-1/3 w-96 h-96 rounded-full bg-coral-500/8 blur-3xl" />
        <div className="absolute top-0 right-1/4 w-64 h-64 rounded-full bg-gold-500/8 blur-3xl" />
      </div>

      <main className="relative z-10 max-w-7xl mx-auto px-4 pt-24 pb-16">
        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <div>
            <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="text-slate-500 text-sm mb-1">
              Welcome back, {user?.email?.split("@")[0] ?? "traveler"}
            </motion.p>
            <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="font-display text-4xl font-semibold gradient-text">
              Your Journeys
            </motion.h1>
          </div>
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
            <Link href="/trips/new">
              <motion.button whileHover={{ scale: 1.04, y: -1 }} whileTap={{ scale: 0.97 }} className="btn-primary flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                New Trip
              </motion.button>
            </Link>
          </motion.div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-32">
            <Loader2 className="w-8 h-8 text-coral-500 animate-spin" />
          </div>
        ) : !trips || trips.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {upcoming.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                    <MapPin className="w-3 h-3" /> Upcoming
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {upcoming.map((t, i) => <TripCard key={t.id} trip={t} index={i} onDelete={setDeleteConfirmId} />)}
                  </div>
                </div>
              )}

              {past.length > 0 && (
                <div className="mt-6">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">Past Trips</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {past.map((t, i) => <TripCard key={t.id} trip={t} index={upcoming.length + i} onDelete={setDeleteConfirmId} />)}
                  </div>
                </div>
              )}
            </div>

            {/* World sidebar */}
            <div className="hidden lg:block lg:col-span-1">
              <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3, duration: 0.5 }}>
                <WorldPanel trips={trips} />

                <div className="glass-card p-5 mt-4">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">Your Travel DNA</p>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: "Trips planned", value: trips.length, color: "text-coral-600" },
                      { label: "Nights away", value: trips.reduce((acc, t) => acc + Math.max(1, Math.ceil((new Date(t.end_date).getTime() - new Date(t.start_date).getTime()) / 86400000)), 0), color: "text-gold-500" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="glass-light rounded-xl p-3 text-center">
                        <p className={`text-2xl font-bold ${color}`}>{value}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{label}</p>
                      </div>
                    ))}
                  </div>
                  <Link href="/profile" className="mt-4 flex items-center justify-between text-xs text-slate-400 hover:text-coral-600 transition-colors group">
                    <span>View full profile</span>
                    <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                  </Link>
                </div>
              </motion.div>
            </div>
          </div>
        )}
      </main>

      {/* Delete confirmation modal */}
      <AnimatePresence>
        {deleteConfirmId && (
          <motion.div
            key="delete-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/40 backdrop-blur-sm"
            onClick={() => setDeleteConfirmId(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 8 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 8 }}
              transition={{ type: "spring", damping: 28, stiffness: 340 }}
              className="glass-card p-6 w-full max-w-sm"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-10 h-10 rounded-xl bg-coral-500/15 border border-coral-500/30 flex items-center justify-center mb-4">
                <Trash2 className="w-5 h-5 text-coral-600" />
              </div>
              <h3 className="text-base font-semibold text-slate-100 mb-1">Delete this trip?</h3>
              <p className="text-sm text-slate-400 mb-6">
                {`"${trips?.find((t) => t.id === deleteConfirmId)?.title ?? "This trip"}" will be permanently removed.`}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteConfirmId(null)}
                  className="flex-1 py-2 rounded-xl text-sm text-slate-400 border border-ink-900/10 hover:bg-ink-900/5 transition-colors"
                >
                  Cancel
                </button>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={handleDeleteConfirm}
                  disabled={deleting}
                  className="flex-1 py-2 rounded-xl text-sm font-semibold text-coral-600 bg-coral-500/15 border border-coral-500/30 hover:bg-coral-500/25 transition-colors disabled:opacity-50"
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
