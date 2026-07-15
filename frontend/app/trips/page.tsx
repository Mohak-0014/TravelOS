"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Calendar, Users, DollarSign, Sparkles, Clock, AlertCircle, Loader2, ArrowRight, Globe2, Trash2 } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { TripOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import NavBar from "@/components/ui/NavBar";
import { Card } from "@/components/ui/Card";
import { CoverArt } from "@/components/ui/CoverArt";
import { Globe } from "@/components/ui/Globe";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Stat } from "@/components/ui/Stat";
import { Modal } from "@/components/ui/Modal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { TiltCard } from "@/components/ui/TiltCard";
import { EASE } from "@/lib/motion";

// ── Trip Card ─────────────────────────────────────────────────────────────────

function TripCard({ trip, index, onDelete }: { trip: TripOut; index: number; onDelete: (id: string) => void }) {
  const nights = Math.max(1, Math.ceil((new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) / 86400000));
  const daysUntil = Math.ceil((new Date(trip.start_date).getTime() - Date.now()) / 86400000);
  const isUpcoming = daysUntil > 0;

  return (
    <motion.div
      className="relative group/card"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4, ease: EASE }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
    >
      <Link href={`/trips/${trip.id}`} className="block" style={{ perspective: 1000 }}>
        <TiltCard intensity={5}>
          <Card padding="none" hover className="overflow-hidden cursor-pointer hover:shadow-glow transition-shadow duration-300">
            <CoverArt city={trip.destination_city} country={trip.destination_country} imageUrl={trip.cover_image_url} height="h-36">
              <div className="flex items-end justify-between w-full h-full p-4">
                <div>
                  <p className="text-white/80 text-xs font-mono uppercase tracking-widest mb-0.5">
                    {isUpcoming ? `${daysUntil}d away` : (trip.destination_country ?? "")}
                  </p>
                  <h2 className="text-white font-display font-medium text-xl leading-tight">{trip.destination_city}</h2>
                </div>
                {trip.status === "awaiting_approval" && (
                  <Badge tone="danger" icon={AlertCircle}>
                    Review
                  </Badge>
                )}
              </div>
            </CoverArt>

            {/* Card body */}
            <div className="p-4">
              <div className="flex items-start justify-between mb-3 gap-2">
                <h3 className="text-ink-900 font-medium text-sm leading-snug flex-1">{trip.title}</h3>
                <StatusBadge status={trip.status} className="shrink-0" />
              </div>

              <div className="flex flex-wrap gap-3 text-xs font-mono text-ink-400">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {new Date(trip.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  {" – "}
                  {new Date(trip.end_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {nights} nights
                </span>
                {trip.num_travelers > 1 && (
                  <span className="flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    {trip.num_travelers}
                  </span>
                )}
                {trip.budget_total && (
                  <span className="flex items-center gap-1">
                    <DollarSign className="w-3 h-3" />
                    {trip.budget_currency} {trip.budget_total.toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          </Card>
        </TiltCard>
      </Link>

      {/* Delete button — visible on card hover */}
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onDelete(trip.id);
        }}
        title="Delete trip"
        className="absolute top-2 right-2 z-10 p-1.5 rounded-lg glass text-white/80 opacity-0 group-hover/card:opacity-100 hover:text-danger transition-all duration-200"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  );
}

// ── "Your World" panel (route-stops list, real trip coordinates) ─────────────

function formatCoord(lat: number, lng: number): string {
  return `${Math.abs(lat).toFixed(1)}°${lat >= 0 ? "N" : "S"} ${Math.abs(lng).toFixed(1)}°${lng >= 0 ? "E" : "W"}`;
}

function WorldPanel({ trips }: { trips: TripOut[] }) {
  const all = trips.filter((t) => t.status === "planned" || t.status === "completed");
  const withCoords = all.filter((t) => t.latitude != null && t.longitude != null);
  const markers = withCoords.map((t) => ({
    location: [t.latitude as number, t.longitude as number] as [number, number],
    size: 0.1,
  }));
  // Open the globe facing the user's trips instead of the default meridian.
  const focus = withCoords[0] ? ([withCoords[0].latitude, withCoords[0].longitude] as [number, number]) : undefined;
  const dests = all.slice(0, 4);
  const overflow = all.length - dests.length;

  return (
    <Card>
      <div className="flex items-center gap-2 mb-1">
        <Globe2 className="w-4 h-4 text-accent" />
        <span className="text-sm font-medium text-ink-900">Your World</span>
      </div>
      <p className="text-xs text-ink-400 mb-5">
        {trips.length} trip{trips.length !== 1 ? "s" : ""} planned
      </p>

      {markers.length > 0 && <Globe markers={markers} focus={focus} size={240} className="mb-6" />}

      {dests.length > 0 ? (
        <div className="relative pl-4">
          <div className="absolute left-[3px] top-1.5 bottom-1.5 border-l border-dashed border-ink-900/15" />
          <div className="space-y-4">
            {dests.map((t) => (
              <div key={t.id} className="relative flex items-start justify-between gap-3">
                <span className="absolute -left-4 top-1.5 w-1.5 h-1.5 rounded-full bg-accent ring-[3px] ring-accent-tint" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink-900 leading-tight truncate">{t.destination_city}</p>
                  {t.destination_country && <p className="text-[11px] text-ink-300 mt-0.5">{t.destination_country}</p>}
                </div>
                {t.latitude != null && t.longitude != null && (
                  <span className="font-mono text-[10px] text-ink-300 shrink-0 tabular-nums pt-0.5">
                    {formatCoord(t.latitude, t.longitude)}
                  </span>
                )}
              </div>
            ))}
            {overflow > 0 && (
              <div className="relative">
                <span className="absolute -left-4 top-1.5 w-1.5 h-1.5 rounded-full bg-ink-200" />
                <p className="text-xs text-ink-300">
                  +{overflow} more trip{overflow !== 1 ? "s" : ""}
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-center px-4">
          <Globe2 className="w-8 h-8 text-ink-200" />
          <p className="text-xs text-ink-300">Your planned trips will appear here on the globe.</p>
        </div>
      )}
    </Card>
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
  const totalNights =
    trips?.reduce(
      (acc, t) => acc + Math.max(1, Math.ceil((new Date(t.end_date).getTime() - new Date(t.start_date).getTime()) / 86400000)),
      0,
    ) ?? 0;

  return (
    <div className="relative min-h-screen bg-paper overflow-x-clip">
      <NavBar />

      {/* Warm ambient bloom behind the header */}
      <div
        className="absolute left-1/2 top-0 -translate-x-1/2 w-[1100px] h-[420px] pointer-events-none"
        style={{ background: "radial-gradient(55% 70% at 50% 0%, rgba(255,158,100,0.07) 0%, transparent 70%)" }}
      />

      <main className="relative z-10 max-w-7xl mx-auto px-4 pt-24 pb-16">
        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <div>
            <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="text-ink-400 text-sm mb-1">
              Welcome back, {user?.email?.split("@")[0] ?? "traveler"}
            </motion.p>
            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="font-display text-4xl font-medium text-ink-900"
            >
              Your Journeys
            </motion.h1>
          </div>
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
            <Link href="/trips/new">
              <Button iconLeft={Sparkles}>New Trip</Button>
            </Link>
          </motion.div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-32">
            <Loader2 className="w-8 h-8 text-accent animate-spin" />
          </div>
        ) : !trips || trips.length === 0 ? (
          <EmptyState
            icon={Globe2}
            title="Where to next?"
            body="Tell TravelOS where you want to go. It handles the rest — and gets smarter every trip."
            action={
              <Link href="/trips/new">
                <Button iconLeft={Sparkles} iconRight={ArrowRight} className="mt-2">
                  Plan my first trip
                </Button>
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {upcoming.length > 0 && (
                <div>
                  <SectionHeader eyebrow="Upcoming" />
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {upcoming.map((t, i) => (
                      <TripCard key={t.id} trip={t} index={i} onDelete={setDeleteConfirmId} />
                    ))}
                  </div>
                </div>
              )}

              {past.length > 0 && (
                <div className="mt-6">
                  <SectionHeader eyebrow="Past Trips" />
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {past.map((t, i) => (
                      <TripCard key={t.id} trip={t} index={upcoming.length + i} onDelete={setDeleteConfirmId} />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* World sidebar */}
            <div className="hidden lg:block lg:col-span-1">
              <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3, duration: 0.5 }}>
                <WorldPanel trips={trips} />

                <Card className="mt-4">
                  <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-4">Your Travel DNA</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-ink-100 rounded-lg p-3 text-center">
                      <Stat label="Trips" value={trips.length} tone="accent" />
                    </div>
                    <div className="bg-ink-100 rounded-lg p-3 text-center">
                      <Stat label="Nights away" value={totalNights} tone="accent" />
                    </div>
                  </div>
                  <Link
                    href="/profile"
                    className="mt-4 flex items-center justify-between text-xs text-ink-400 hover:text-accent transition-colors group"
                  >
                    <span>View full profile</span>
                    <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                  </Link>
                </Card>
              </motion.div>
            </div>
          </div>
        )}
      </main>

      {/* Delete confirmation modal */}
      <Modal
        open={!!deleteConfirmId}
        onClose={() => setDeleteConfirmId(null)}
        width="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDeleteConfirm} loading={deleting}>
              Delete
            </Button>
          </>
        }
      >
        <div className="w-10 h-10 rounded-lg bg-danger-tint flex items-center justify-center mb-4">
          <Trash2 className="w-5 h-5 text-danger" />
        </div>
        <h3 className="font-display text-base font-medium text-ink-900 mb-1">Delete this trip?</h3>
        <p className="text-sm text-ink-400">
          {`"${trips?.find((t) => t.id === deleteConfirmId)?.title ?? "This trip"}" will be permanently removed.`}
        </p>
      </Modal>
    </div>
  );
}
