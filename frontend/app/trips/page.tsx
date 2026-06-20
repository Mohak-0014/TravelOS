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
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import type { TripOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import NavBar from "@/components/ui/NavBar";

const StarField = dynamic(() => import("@/components/3d/StarField"), { ssr: false });
const TravelGlobe = dynamic(() => import("@/components/3d/TravelGlobe"), { ssr: false });

// ── Status config ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: typeof CheckCircle2; glow: string }> = {
  planning:         { label: "Planning",          color: "text-gold-400 bg-gold/10 border-gold/20",        icon: Clock,          glow: "shadow-gold-sm" },
  generating:       { label: "Generating…",       color: "text-electric-400 bg-electric-500/10 border-electric-500/20", icon: Loader2, glow: "shadow-electric-sm animate-pulse" },
  awaiting_approval:{ label: "Your Call",         color: "text-coral-400 bg-coral-500/10 border-coral-500/20", icon: AlertCircle, glow: "shadow-coral-sm" },
  planned:          { label: "Ready",             color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20", icon: CheckCircle2, glow: "" },
  completed:        { label: "Completed",         color: "text-slate-400 bg-slate-700/30 border-slate-700/30", icon: CheckCircle2, glow: "" },
};

// ── Destination image helper ───────────────────────────────────────────────────

const DEST_GRADIENTS = [
  "from-blue-900 via-indigo-800 to-purple-900",
  "from-emerald-900 via-teal-800 to-cyan-900",
  "from-orange-900 via-rose-800 to-pink-900",
  "from-violet-900 via-purple-800 to-pink-900",
  "from-sky-900 via-blue-800 to-indigo-900",
  "from-amber-900 via-orange-800 to-red-900",
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
  const daysUntil = Math.ceil(
    (new Date(trip.start_date).getTime() - Date.now()) / 86400000
  );
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
        <div className="glass-card overflow-hidden cursor-pointer transition-all duration-300 hover:border-electric-500/30 hover:shadow-card-hover">
          {/* Destination banner — real photo or gradient fallback */}
          <div
            className={`relative h-24 bg-gradient-to-br ${gradient} flex items-end p-4`}
            style={trip.cover_image_url ? {
              backgroundImage: `url(${trip.cover_image_url})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
            } : undefined}
          >
            {trip.cover_image_url && <div className="absolute inset-0 bg-black/35" />}
            <div className="relative z-10 flex items-end justify-between w-full">
              <div>
                <p className="text-white/70 text-xs font-medium uppercase tracking-widest mb-0.5">
                  {isUpcoming ? `${daysUntil}d away` : trip.destination_country ?? ""}
                </p>
                <h2 className="text-white font-bold text-xl leading-tight">{trip.destination_city}</h2>
              </div>
              {trip.status === "awaiting_approval" && (
                <div className="flex items-center gap-1 bg-coral-500/90 text-white text-xs font-bold px-2.5 py-1 rounded-full animate-pulse">
                  <AlertCircle className="w-3 h-3" />
                  Review
                </div>
              )}
            </div>
          </div>

          {/* Card body */}
          <div className="p-4">
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-slate-100 font-semibold text-sm leading-snug flex-1 mr-2">
                {trip.title}
              </h3>
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
        className="absolute top-2 right-2 z-10 p-1.5 rounded-lg bg-space-900/80 backdrop-blur-sm text-slate-500 opacity-0 group-hover/card:opacity-100 hover:text-coral-400 hover:bg-coral-500/10 transition-all duration-200"
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
      <h3 className="text-2xl font-bold text-slate-100 mb-2">Where to next?</h3>
      <p className="text-slate-400 mb-8 max-w-xs mx-auto leading-relaxed">
        Tell TravelOS where you want to go. It handles the rest — and gets smarter every trip.
      </p>
      <Link href="/trips/new">
        <motion.button
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.98 }}
          className="btn-primary flex items-center gap-2 mx-auto"
        >
          <Sparkles className="w-4 h-4" />
          Plan my first trip
          <ArrowRight className="w-4 h-4" />
        </motion.button>
      </Link>
    </motion.div>
  );
}

// ── Globe panel ───────────────────────────────────────────────────────────────

function GlobePanel({ trips }: { trips: TripOut[] }) {
  const points = trips
    .filter((t) => t.status === "planned" || t.status === "completed")
    .slice(0, 12)
    .map((t) => ({
      lat: 48 + Math.sin(t.destination_city.length) * 20,
      lng: 2 + Math.cos(t.destination_city.length * 2) * 80,
      label: t.destination_city,
      size: 0.5,
      color: t.status === "completed" ? "#10b981" : "#3b82f6",
    }));

  return (
    <div className="glass-card p-6 flex flex-col items-center">
      <div className="flex items-center gap-2 mb-1 self-start">
        <Globe2 className="w-4 h-4 text-electric-400" />
        <span className="text-sm font-semibold text-slate-200">Your World</span>
      </div>
      <p className="text-xs text-slate-500 self-start mb-4">{trips.length} trip{trips.length !== 1 ? "s" : ""} planned</p>
      <TravelGlobe points={points.length ? points : undefined} width={300} height={300} />
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
      <StarField />
      <NavBar />

      {/* Hero gradient */}
      <div className="absolute top-0 left-0 right-0 h-96 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/3 w-96 h-96 rounded-full bg-electric-500/8 blur-3xl" />
        <div className="absolute top-0 right-1/4 w-64 h-64 rounded-full bg-purple-600/8 blur-3xl" />
      </div>

      <main className="relative z-10 max-w-7xl mx-auto px-4 pt-24 pb-16">
        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <div>
            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-slate-500 text-sm mb-1"
            >
              Welcome back, {user?.email?.split("@")[0] ?? "traveler"}
            </motion.p>
            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="text-3xl font-bold gradient-text"
            >
              Your Journeys
            </motion.h1>
          </div>
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Link href="/trips/new">
              <motion.button
                whileHover={{ scale: 1.04, y: -1 }}
                whileTap={{ scale: 0.97 }}
                className="btn-primary flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                New Trip
              </motion.button>
            </Link>
          </motion.div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-32">
            <Loader2 className="w-8 h-8 text-electric-400 animate-spin" />
          </div>
        ) : !trips || trips.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Trip grid */}
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
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
                    Past Trips
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {past.map((t, i) => <TripCard key={t.id} trip={t} index={upcoming.length + i} onDelete={setDeleteConfirmId} />)}
                  </div>
                </div>
              )}
            </div>

            {/* Globe sidebar — hidden on mobile, shown on large screens */}
            <div className="hidden lg:block lg:col-span-1">
              <motion.div
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3, duration: 0.5 }}
              >
                <GlobePanel trips={trips} />

                {/* Quick stats */}
                <div className="glass-card p-5 mt-4">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
                    Your Travel DNA
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: "Trips planned", value: trips.length, color: "text-electric-400" },
                      { label: "Nights away", value: trips.reduce((acc, t) => acc + Math.max(1, Math.ceil((new Date(t.end_date).getTime() - new Date(t.start_date).getTime()) / 86400000)), 0), color: "text-gold-400" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="glass-light rounded-xl p-3 text-center">
                        <p className={`text-2xl font-bold ${color}`}>{value}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{label}</p>
                      </div>
                    ))}
                  </div>
                  <Link href="/profile" className="mt-4 flex items-center justify-between text-xs text-slate-400 hover:text-electric-400 transition-colors group">
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
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
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
                <Trash2 className="w-5 h-5 text-coral-400" />
              </div>
              <h3 className="text-base font-semibold text-slate-100 mb-1">Delete this trip?</h3>
              <p className="text-sm text-slate-400 mb-6">
                {`"${trips?.find((t) => t.id === deleteConfirmId)?.title ?? "This trip"}" will be permanently removed.`}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteConfirmId(null)}
                  className="flex-1 py-2 rounded-xl text-sm text-slate-400 border border-white/10 hover:bg-white/5 transition-colors"
                >
                  Cancel
                </button>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={handleDeleteConfirm}
                  disabled={deleting}
                  className="flex-1 py-2 rounded-xl text-sm font-semibold text-coral-400 bg-coral-500/15 border border-coral-500/30 hover:bg-coral-500/25 transition-colors disabled:opacity-50"
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
