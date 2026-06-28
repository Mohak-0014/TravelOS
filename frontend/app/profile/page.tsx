"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Zap,
  Heart,
  Star,
  TrendingUp,
  Settings,
  LogOut,
  CheckCircle2,
  Map,
  Calendar,
  User,
  Check,
  Landmark,
  Mountain,
  Utensils,
  Leaf,
  Moon,
  Palette,
  BookOpen,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { TripOut, PreferenceOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import NavBar from "@/components/ui/NavBar";

// ── Travel personality badge ──────────────────────────────────────────────────

function computePersonality(prefs: PreferenceOut | null | undefined): {
  label: string;
  emoji: string;
  desc: string;
  color: string;
} {
  if (!prefs) {
    return {
      label: "The Curious Traveler",
      emoji: "✦",
      desc: "An explorer in the making.",
      color: "from-electric-400 to-purple-400",
    };
  }
  const { pace, budget_behavior, luxury_tier } = prefs;
  if (pace === "relaxed" && budget_behavior === "frugal") {
    return {
      label: "The Mindful Wanderer",
      emoji: "🌿",
      desc: "Slow, intentional journeys. Quality over quantity.",
      color: "from-emerald-400 to-teal-400",
    };
  }
  if (pace === "packed" && luxury_tier === "luxury") {
    return {
      label: "The Power Explorer",
      emoji: "⚡",
      desc: "Maximum destinations, maximum comfort.",
      color: "from-gold-400 to-orange-400",
    };
  }
  if (pace === "moderate" && budget_behavior === "splurge") {
    return {
      label: "The Immersive Seeker",
      emoji: "🎭",
      desc: "Deep experiences over broad coverage.",
      color: "from-coral-400 to-pink-400",
    };
  }
  return {
    label: "The Curious Traveler",
    emoji: "✦",
    desc: "An adventurer with an open itinerary.",
    color: "from-electric-400 to-purple-400",
  };
}

// ── Animated count-up ─────────────────────────────────────────────────────────

function CountUp({ target, duration = 1200 }: { target: number; duration?: number }) {
  const [value, setValue] = useState(0);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    if (target === 0) return;
    const start = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return <>{value}</>;
}

// ── Ring progress ─────────────────────────────────────────────────────────────

function RingProgress({ value, max, size = 80, stroke = 6, color = "#60a5fa" }: {
  value: number;
  max: number;
  size?: number;
  stroke?: number;
  color?: string;
}) {
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = Math.min(value / max, 1);
  const offset = circumference * (1 - pct);

  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1s ease" }}
      />
    </svg>
  );
}

// ── Preference slider ─────────────────────────────────────────────────────────

type PrefKey = "pace" | "luxury_tier" | "budget_behavior";

interface SliderConfig {
  key: PrefKey;
  label: string;
  leftLabel: string;
  rightLabel: string;
  values: string[];
  icon: typeof Brain;
  color: string;
}

const PREFERENCE_SLIDERS: SliderConfig[] = [
  {
    key: "pace",
    label: "Travel Pace",
    leftLabel: "Relaxed",
    rightLabel: "Packed",
    values: ["relaxed", "moderate", "packed"],
    icon: Zap,
    color: "electric",
  },
  {
    key: "luxury_tier",
    label: "Comfort Level",
    leftLabel: "Budget",
    rightLabel: "Luxury",
    values: ["budget", "mid", "luxury"],
    icon: Star,
    color: "gold",
  },
  {
    key: "budget_behavior",
    label: "Spending Style",
    leftLabel: "Frugal",
    rightLabel: "Splurge",
    values: ["frugal", "balanced", "splurge"],
    icon: TrendingUp,
    color: "coral",
  },
];

const COLOR_MAP: Record<string, string> = {
  electric: "bg-electric-500 shadow-electric-sm",
  gold: "bg-gold-500 shadow-gold-sm",
  coral: "bg-coral-500 shadow-coral-sm",
};

const TRACK_COLOR_MAP: Record<string, string> = {
  electric: "bg-electric-500/30",
  gold: "bg-gold-500/30",
  coral: "bg-coral-500/30",
};

const INTERESTS = [
  { id: "culture", label: "Culture", icon: Landmark },
  { id: "adventure", label: "Adventure", icon: Mountain },
  { id: "food", label: "Food & Drink", icon: Utensils },
  { id: "nature", label: "Nature", icon: Leaf },
  { id: "nightlife", label: "Nightlife", icon: Moon },
  { id: "art", label: "Art & Museums", icon: Palette },
  { id: "history", label: "History", icon: BookOpen },
  { id: "wellness", label: "Wellness", icon: Heart },
];

const FOOD_PREFS = [
  { id: "local_cuisine", label: "Local Cuisine", emoji: "🌍" },
  { id: "street_food", label: "Street Food", emoji: "🌮" },
  { id: "fine_dining", label: "Fine Dining", emoji: "🍽️" },
  { id: "vegetarian", label: "Vegetarian", emoji: "🥦" },
  { id: "vegan", label: "Vegan", emoji: "🌱" },
  { id: "seafood", label: "Seafood", emoji: "🦞" },
  { id: "halal", label: "Halal", emoji: "☪️" },
  { id: "kosher", label: "Kosher", emoji: "✡️" },
];

function PreferenceSlider({
  config,
  value,
  onChange,
}: {
  config: SliderConfig;
  value: string | null;
  onChange: (key: PrefKey, val: string) => void;
}) {
  const Icon = config.icon;
  const activeIdx = value ? config.values.indexOf(value) : 1;
  const safeIdx = activeIdx < 0 ? 1 : activeIdx;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-widest">
          {config.label}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-slate-500 w-14 text-right">{config.leftLabel}</span>
        <div className="flex-1 flex items-center gap-1.5">
          {config.values.map((v, i) => (
            <button
              key={v}
              onClick={() => onChange(config.key, v)}
              className={`flex-1 h-2 rounded-full transition-all duration-300 ${
                i === safeIdx
                  ? COLOR_MAP[config.color]
                  : i < safeIdx
                  ? TRACK_COLOR_MAP[config.color]
                  : "bg-ink-900/[0.05]"
              }`}
            />
          ))}
        </div>
        <span className="text-xs text-slate-500 w-14">{config.rightLabel}</span>
      </div>
      <div className="flex justify-between px-[4.25rem]">
        {config.values.map((v, i) => (
          <span
            key={v}
            className={`text-[10px] transition-colors ${
              i === safeIdx ? "text-slate-200 font-medium" : "text-slate-600"
            }`}
          >
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Status config ─────────────────────────────────────────────────────────────

const STATUS_BADGES: Record<string, { label: string; cls: string }> = {
  planning: { label: "Planning", cls: "text-gold-400 bg-gold-400/10 border-gold-400/20" },
  generating: { label: "Generating", cls: "text-electric-400 bg-electric-400/10 border-electric-400/20" },
  awaiting_approval: { label: "Your Call", cls: "text-coral-400 bg-coral-400/10 border-coral-400/20" },
  planned: { label: "Ready", cls: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" },
  completed: { label: "Done", cls: "text-slate-400 bg-slate-400/10 border-slate-400/20" },
};

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, user, logout, _hasHydrated } = useAuthStore();

  // Local preference state for optimistic editing
  const [localPrefs, setLocalPrefs] = useState<Partial<Record<PrefKey, string>>>({});
  const [localInterests, setLocalInterests] = useState<Set<string>>(new Set());
  const [localFoodPrefs, setLocalFoodPrefs] = useState<Set<string>>(new Set());
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    if (_hasHydrated && !token) router.replace("/login");
  }, [_hasHydrated, token, router]);

  const { data: prefs } = useQuery<PreferenceOut>({
    queryKey: ["preferences"],
    queryFn: () => api.get<PreferenceOut>("/api/v1/preferences"),
    enabled: !!token,
    retry: false,
  });

  const { data: trips } = useQuery<TripOut[]>({
    queryKey: ["trips"],
    queryFn: () => api.get<TripOut[]>("/api/v1/trips"),
    enabled: !!token,
  });

  // Sync local prefs when server prefs load
  useEffect(() => {
    if (prefs) {
      setLocalPrefs({
        pace: prefs.pace ?? "moderate",
        luxury_tier: prefs.luxury_tier ?? "mid",
        budget_behavior: prefs.budget_behavior ?? "balanced",
      });
      setLocalInterests(new Set(prefs.interests ?? []));
      setLocalFoodPrefs(new Set(prefs.food_prefs ?? []));
    }
  }, [prefs]);

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.put("/api/v1/preferences", body),
    onMutate: () => setSaveStatus("saving"),
    onSuccess: () => {
      setSaveStatus("saved");
      queryClient.invalidateQueries({ queryKey: ["preferences"] });
      setTimeout(() => setSaveStatus("idle"), 2500);
    },
    onError: () => {
      setSaveStatus("error");
      setTimeout(() => setSaveStatus("idle"), 2500);
    },
  });

  const handlePrefChange = useCallback((key: PrefKey, val: string) => {
    setLocalPrefs((prev) => ({ ...prev, [key]: val }));
    setSaveStatus("idle");
  }, []);

  const handleSave = () => {
    mutation.mutate({
      ...localPrefs,
      interests: Array.from(localInterests),
      food_prefs: Array.from(localFoodPrefs),
    });
  };

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  if (!_hasHydrated) return null;

  // Merge server + local for personality computation
  const mergedPrefs: PreferenceOut | null = prefs
    ? { ...prefs, ...localPrefs }
    : null;

  const personality = computePersonality(mergedPrefs);
  const decisionsLearned = Math.max(0, (trips?.length ?? 0) * 4 + 7);
  const confidencePct = Math.min(decisionsLearned, 50);

  return (
    <div className="relative min-h-screen bg-space-900">
      <div className="absolute top-0 left-0 right-0 h-96 pointer-events-none overflow-hidden">
        <div className="absolute inset-0 bg-sky-gradient opacity-60" />
        <div className="absolute top-10 left-1/3 w-96 h-96 rounded-full bg-coral-500/8 blur-3xl" />
        <div className="absolute top-0 right-1/4 w-72 h-72 rounded-full bg-gold-500/8 blur-3xl" />
      </div>
      <NavBar />

      {/* Ambient glows */}
      <div className="absolute top-0 left-0 right-0 h-[500px] pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] rounded-full bg-electric-500/6 blur-[120px]" />
        <div className="absolute top-20 right-1/4 w-80 h-80 rounded-full bg-purple-600/6 blur-[100px]" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full bg-gold-500/4 blur-[120px]" />
      </div>

      <main className="relative z-10 max-w-5xl mx-auto px-4 pt-24 pb-20">

        {/* ── HERO ─────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mb-10"
        >
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-slate-500 text-sm mb-1 flex items-center gap-2">
                <User className="w-3.5 h-3.5" />
                {user?.email}
              </p>
              <h1 className="text-4xl md:text-5xl font-bold gradient-text leading-tight mb-4">
                Your Travel DNA
              </h1>
            </div>

            {/* Personality badge */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, duration: 0.4 }}
              className="glass-card px-5 py-3.5 flex items-center gap-3"
            >
              <div
                className={`w-10 h-10 rounded-xl bg-gradient-to-br ${personality.color} flex items-center justify-center text-lg shadow-electric-sm`}
              >
                {personality.emoji}
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-widest mb-0.5">
                  Travel Persona
                </p>
                <p className="text-sm font-bold text-slate-100">{personality.label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{personality.desc}</p>
              </div>
            </motion.div>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

          {/* LEFT COLUMN — preferences + past trips */}
          <div className="lg:col-span-3 space-y-6">

            {/* ── PREFERENCES ────────────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="glass-card p-6"
            >
              <div className="flex items-center gap-2 mb-6">
                <div className="w-7 h-7 rounded-lg bg-electric-gradient flex items-center justify-center shadow-electric-sm">
                  <Settings className="w-3.5 h-3.5 text-white" />
                </div>
                <h2 className="font-bold text-slate-100">Travel Preferences</h2>
                <span className="ml-auto text-xs text-slate-500">
                  AI uses these to personalise every trip
                </span>
              </div>

              <div className="space-y-6">
                {PREFERENCE_SLIDERS.map((cfg) => (
                  <PreferenceSlider
                    key={cfg.key}
                    config={cfg}
                    value={localPrefs[cfg.key] ?? prefs?.[cfg.key] ?? null}
                    onChange={handlePrefChange}
                  />
                ))}
              </div>

              {/* ── Interests ─────────────────────────────────────── */}
              <div className="pt-6 border-t border-ink-900/8">
                <div className="flex items-center gap-2 mb-3">
                  <Heart className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-widest">
                    Interests
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {INTERESTS.map(({ id, label, icon: Icon }) => {
                    const selected = localInterests.has(id);
                    return (
                      <button
                        key={id}
                        onClick={() =>
                          setLocalInterests((prev) => {
                            const next = new Set(prev);
                            if (next.has(id)) next.delete(id);
                            else next.add(id);
                            return next;
                          })
                        }
                        className={`flex items-center gap-2 p-2.5 rounded-xl border text-left text-xs transition-all ${
                          selected
                            ? "border-electric-500/50 bg-electric-500/12 text-slate-100"
                            : "border-ink-900/10 bg-ink-900/[0.03] text-slate-400 hover:bg-ink-900/[0.05]"
                        }`}
                      >
                        <Icon
                          className={`w-3.5 h-3.5 shrink-0 ${selected ? "text-electric-400" : ""}`}
                        />
                        <span className="font-medium">{label}</span>
                        {selected && (
                          <Check className="w-3 h-3 text-electric-400 ml-auto shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* ── Food Preferences ──────────────────────────────── */}
              <div className="pt-6 border-t border-ink-900/8">
                <div className="flex items-center gap-2 mb-3">
                  <Utensils className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-widest">
                    Food Preferences
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {FOOD_PREFS.map(({ id, label, emoji }) => {
                    const selected = localFoodPrefs.has(id);
                    return (
                      <button
                        key={id}
                        onClick={() =>
                          setLocalFoodPrefs((prev) => {
                            const next = new Set(prev);
                            if (next.has(id)) next.delete(id);
                            else next.add(id);
                            return next;
                          })
                        }
                        className={`flex items-center gap-2 p-2.5 rounded-xl border text-left text-xs transition-all ${
                          selected
                            ? "border-gold-400/50 bg-gold-400/12 text-slate-100"
                            : "border-ink-900/10 bg-ink-900/[0.03] text-slate-400 hover:bg-ink-900/[0.05]"
                        }`}
                      >
                        <span className="text-sm shrink-0">{emoji}</span>
                        <span className="font-medium">{label}</span>
                        {selected && (
                          <Check className="w-3 h-3 text-gold-400 ml-auto shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center gap-3 mt-7 pt-5 border-t border-ink-900/8">
                <motion.button
                  whileHover={{ scale: 1.03, y: -1 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={handleSave}
                  disabled={mutation.isPending}
                  className="btn-primary flex items-center gap-2 text-sm px-5 py-2.5"
                >
                  {saveStatus === "saving" ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                      Saving…
                    </>
                  ) : (
                    <>
                      <Heart className="w-3.5 h-3.5" />
                      Save Preferences
                    </>
                  )}
                </motion.button>

                <AnimatePresence>
                  {saveStatus === "saved" && (
                    <motion.span
                      key="saved"
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      className="flex items-center gap-1.5 text-emerald-400 text-sm"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Saved!
                    </motion.span>
                  )}
                  {saveStatus === "error" && (
                    <motion.span
                      key="error"
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      className="text-coral-400 text-sm"
                    >
                      Could not save — check connection
                    </motion.span>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>

            {/* ── PAST TRIPS ─────────────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="glass-card p-6"
            >
              <div className="flex items-center gap-2 mb-5">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-gold-400 to-orange-400 flex items-center justify-center shadow-gold-sm">
                  <Map className="w-3.5 h-3.5 text-white" />
                </div>
                <h2 className="font-bold text-slate-100">Past Trips</h2>
                <span className="ml-auto text-xs text-slate-500">
                  {trips?.length ?? 0} trips planned
                </span>
              </div>

              {!trips || trips.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-slate-500 text-sm">No trips yet.</p>
                  <Link
                    href="/trips/new"
                    className="text-electric-400 text-sm hover:text-electric-300 mt-1 inline-block transition-colors"
                  >
                    Plan your first trip →
                  </Link>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {trips.map((trip, i) => {
                    const badge = STATUS_BADGES[trip.status] ?? STATUS_BADGES.planning;
                    const nights = Math.max(
                      1,
                      Math.ceil(
                        (new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) /
                          86400000
                      )
                    );
                    return (
                      <motion.div
                        key={trip.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.28 + i * 0.04 }}
                      >
                        <Link href={`/trips/${trip.id}`}>
                          <div className="glass-light rounded-xl px-4 py-3 flex items-center gap-3 hover:border-electric-500/20 hover:bg-ink-900/[0.04] transition-all group cursor-pointer">
                            <div className="w-8 h-8 rounded-lg bg-electric-500/15 flex items-center justify-center shrink-0">
                              <Map className="w-3.5 h-3.5 text-electric-400" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-semibold text-slate-200 truncate">{trip.destination_city}</p>
                              <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
                                <Calendar className="w-3 h-3" />
                                {new Date(trip.start_date).toLocaleDateString("en-US", {
                                  month: "short",
                                  day: "numeric",
                                  year: "numeric",
                                })}
                                <span className="text-slate-600">·</span>
                                {nights}n
                              </p>
                            </div>
                            <span className={`status-badge shrink-0 ${badge.cls}`}>
                              {badge.label}
                            </span>
                          </div>
                        </Link>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </motion.div>
          </div>

          {/* RIGHT COLUMN — memory stats + sign out */}
          <div className="lg:col-span-2 space-y-5">

            {/* ── AI MEMORY STATS GRID ───────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="glass-card p-5"
            >
              <div className="flex items-center gap-2 mb-5">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-electric-sm">
                  <Brain className="w-3.5 h-3.5 text-white" />
                </div>
                <h2 className="font-bold text-slate-100 text-sm">AI Memory</h2>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* Card 1 — Decisions */}
                <div className="glass-light rounded-xl p-4 text-center">
                  <p className="text-2xl font-bold text-electric-400 tabular-nums">
                    <CountUp target={decisionsLearned} />
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1 leading-tight">Decisions<br />learned</p>
                </div>

                {/* Card 2 — Trips */}
                <div className="glass-light rounded-xl p-4 text-center">
                  <p className="text-2xl font-bold text-gold-400 tabular-nums">
                    <CountUp target={trips?.length ?? 0} />
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1 leading-tight">Trips<br />planned</p>
                </div>

                {/* Card 3 — Confidence ring */}
                <div className="glass-light rounded-xl p-4 flex flex-col items-center gap-2">
                  <div className="relative">
                    <RingProgress value={confidencePct} max={50} size={56} stroke={5} color="#a78bfa" />
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-purple-400">
                      {Math.round((confidencePct / 50) * 100)}%
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 text-center leading-tight">
                    Personalisation<br />confidence
                  </p>
                </div>

                {/* Card 4 — Learning pulse */}
                <div className="glass-light rounded-xl p-4 flex flex-col items-center justify-center gap-2.5">
                  <div className="relative flex items-center justify-center">
                    <div className="absolute w-8 h-8 rounded-full bg-emerald-400/20 animate-ping" />
                    <div className="w-4 h-4 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)]" />
                  </div>
                  <p className="text-[11px] text-slate-500 text-center leading-tight">
                    AI is learning<br />from you
                  </p>
                </div>
              </div>

              <p className="text-[11px] text-slate-600 text-center mt-4">
                Confidence maxes out at 50 decisions. Keep planning!
              </p>
            </motion.div>

            {/* ── QUICK LINKS ───────────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="glass-card p-5 space-y-3"
            >
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
                Quick Actions
              </h3>

              <Link href="/trips">
                <motion.div
                  whileHover={{ x: 3 }}
                  className="flex items-center gap-3 px-4 py-3 glass-light rounded-xl cursor-pointer hover:border-electric-500/20 transition-all group"
                >
                  <Map className="w-4 h-4 text-electric-400" />
                  <span className="text-sm text-slate-300 group-hover:text-slate-100 transition-colors">
                    My Trips
                  </span>
                  <span className="ml-auto text-slate-600 group-hover:text-slate-400 text-xs">→</span>
                </motion.div>
              </Link>

              <Link href="/trips/new">
                <motion.div
                  whileHover={{ x: 3 }}
                  className="flex items-center gap-3 px-4 py-3 glass-light rounded-xl cursor-pointer hover:border-gold-400/20 transition-all group"
                >
                  <Zap className="w-4 h-4 text-gold-400" />
                  <span className="text-sm text-slate-300 group-hover:text-slate-100 transition-colors">
                    Plan New Trip
                  </span>
                  <span className="ml-auto text-slate-600 group-hover:text-slate-400 text-xs">→</span>
                </motion.div>
              </Link>
            </motion.div>

            {/* ── SIGN OUT ──────────────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.38, duration: 0.45 }}
            >
              <motion.button
                whileHover={{ scale: 1.02, y: -1 }}
                whileTap={{ scale: 0.97 }}
                onClick={handleLogout}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 glass-light rounded-xl text-slate-400 hover:text-coral-400 hover:border-coral-400/20 transition-all text-sm font-medium border border-ink-900/8"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </motion.button>
            </motion.div>
          </div>
        </div>
      </main>
    </div>
  );
}
