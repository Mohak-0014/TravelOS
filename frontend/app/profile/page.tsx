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
  Leaf,
  Sparkles,
  Compass,
  ArrowRight,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { TripOut, PreferenceOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { INTERESTS, FOOD_PREFS } from "@/lib/constants";
import NavBar from "@/components/ui/NavBar";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { EASE } from "@/lib/motion";

// ── Travel personality badge ──────────────────────────────────────────────────

function computePersonality(prefs: PreferenceOut | null | undefined): {
  label: string;
  icon: LucideIcon;
  desc: string;
} {
  if (!prefs) {
    return { label: "The Curious Traveler", icon: Compass, desc: "An explorer in the making." };
  }
  const { pace, budget_behavior, luxury_tier } = prefs;
  if (pace === "relaxed" && budget_behavior === "frugal") {
    return { label: "The Mindful Wanderer", icon: Leaf, desc: "Slow, intentional journeys. Quality over quantity." };
  }
  if (pace === "packed" && luxury_tier === "luxury") {
    return { label: "The Power Explorer", icon: Zap, desc: "Maximum destinations, maximum comfort." };
  }
  if (pace === "moderate" && budget_behavior === "splurge") {
    return { label: "The Immersive Seeker", icon: Sparkles, desc: "Deep experiences over broad coverage." };
  }
  return { label: "The Curious Traveler", icon: Compass, desc: "An adventurer with an open itinerary." };
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

function RingProgress({
  value,
  max,
  size = 80,
  stroke = 6,
  color = "#FF9E64",
}: {
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
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
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
  icon: LucideIcon;
}

const PREFERENCE_SLIDERS: SliderConfig[] = [
  { key: "pace", label: "Travel Pace", leftLabel: "Relaxed", rightLabel: "Packed", values: ["relaxed", "moderate", "packed"], icon: Zap },
  {
    key: "luxury_tier",
    label: "Comfort Level",
    leftLabel: "Budget",
    rightLabel: "Luxury",
    values: ["budget", "mid", "luxury"],
    icon: Star,
  },
  {
    key: "budget_behavior",
    label: "Spending Style",
    leftLabel: "Frugal",
    rightLabel: "Splurge",
    values: ["frugal", "balanced", "splurge"],
    icon: TrendingUp,
  },
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
        <Icon className="w-3.5 h-3.5 text-ink-400" />
        <span className="font-mono text-xs font-medium text-ink-600 uppercase tracking-wider">{config.label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-ink-400 w-14 text-right">{config.leftLabel}</span>
        <div className="flex-1 flex items-center gap-1.5">
          {config.values.map((v, i) => (
            <button
              key={v}
              onClick={() => onChange(config.key, v)}
              className={`flex-1 h-2 rounded-full transition-colors duration-300 ${
                i === safeIdx ? "bg-accent" : i < safeIdx ? "bg-accent/30" : "bg-ink-100"
              }`}
            />
          ))}
        </div>
        <span className="text-xs text-ink-400 w-14">{config.rightLabel}</span>
      </div>
      <div className="flex justify-between px-[4.25rem]">
        {config.values.map((v, i) => (
          <span key={v} className={`text-[10px] transition-colors ${i === safeIdx ? "text-ink-900 font-medium" : "text-ink-300"}`}>
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </span>
        ))}
      </div>
    </div>
  );
}

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
    mutationFn: (body: Record<string, unknown>) => api.put("/api/v1/preferences", body),
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
  const mergedPrefs: PreferenceOut | null = prefs ? { ...prefs, ...localPrefs } : null;

  const personality = computePersonality(mergedPrefs);
  const PersonalityIcon = personality.icon;
  const decisionsLearned = Math.max(0, (trips?.length ?? 0) * 4 + 7);
  const confidencePct = Math.min(decisionsLearned, 50);

  return (
    <div className="relative min-h-screen bg-paper">
      <NavBar />

      <main className="relative z-10 max-w-5xl mx-auto px-4 pt-24 pb-20">
        {/* ── HERO ─────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE }}
          className="mb-10"
        >
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-ink-400 text-sm mb-1 flex items-center gap-2">
                <User className="w-3.5 h-3.5" />
                {user?.email}
              </p>
              <h1 className="font-display text-4xl md:text-5xl font-medium text-ink-900 leading-tight">Your Travel DNA</h1>
            </div>

            {/* Personality badge */}
            <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2, duration: 0.4 }}>
              <Card className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-accent-tint flex items-center justify-center shrink-0">
                  <PersonalityIcon className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-wider text-ink-400 mb-0.5">Travel Persona</p>
                  <p className="text-sm font-medium text-ink-900">{personality.label}</p>
                  <p className="text-xs text-ink-400 mt-0.5">{personality.desc}</p>
                </div>
              </Card>
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
              transition={{ delay: 0.15, duration: 0.45, ease: EASE }}
            >
              <Card>
                <div className="flex items-center gap-2 mb-6">
                  <div className="w-7 h-7 rounded-lg bg-sunset flex items-center justify-center">
                    <Settings className="w-3.5 h-3.5 text-[#1F1206]" />
                  </div>
                  <h2 className="font-medium text-ink-900">Travel Preferences</h2>
                  <span className="ml-auto text-xs text-ink-400">AI uses these to personalise every trip</span>
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
                <div className="pt-6 mt-6 border-t border-ink-900/10">
                  <div className="flex items-center gap-2 mb-3">
                    <Heart className="w-3.5 h-3.5 text-ink-400" />
                    <span className="font-mono text-xs font-medium text-ink-600 uppercase tracking-wider">Interests</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {INTERESTS.map(({ id, label, icon }) => (
                      <Chip
                        key={id}
                        icon={icon}
                        selected={localInterests.has(id)}
                        onClick={() =>
                          setLocalInterests((prev) => {
                            const next = new Set(prev);
                            if (next.has(id)) next.delete(id);
                            else next.add(id);
                            return next;
                          })
                        }
                        className="w-full justify-start"
                      >
                        {label}
                      </Chip>
                    ))}
                  </div>
                </div>

                {/* ── Food Preferences ──────────────────────────────── */}
                <div className="pt-6 mt-6 border-t border-ink-900/10">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="font-mono text-xs font-medium text-ink-600 uppercase tracking-wider">Food Preferences</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {FOOD_PREFS.map(({ id, label, icon }) => (
                      <Chip
                        key={id}
                        icon={icon}
                        selected={localFoodPrefs.has(id)}
                        onClick={() =>
                          setLocalFoodPrefs((prev) => {
                            const next = new Set(prev);
                            if (next.has(id)) next.delete(id);
                            else next.add(id);
                            return next;
                          })
                        }
                        className="w-full justify-start"
                      >
                        {label}
                      </Chip>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-3 mt-7 pt-5 border-t border-ink-900/10">
                  <Button onClick={handleSave} loading={saveStatus === "saving"} iconLeft={Heart}>
                    Save Preferences
                  </Button>

                  <AnimatePresence>
                    {saveStatus === "saved" && (
                      <motion.span
                        key="saved"
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center gap-1.5 text-success text-sm"
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
                        className="text-danger text-sm"
                      >
                        Could not save — check connection
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
              </Card>
            </motion.div>

            {/* ── PAST TRIPS ─────────────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25, duration: 0.45, ease: EASE }}
            >
              <Card>
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 rounded-lg bg-sunset flex items-center justify-center">
                    <Map className="w-3.5 h-3.5 text-[#1F1206]" />
                  </div>
                  <h2 className="font-medium text-ink-900">Past Trips</h2>
                  <span className="ml-auto text-xs text-ink-400">{trips?.length ?? 0} trips planned</span>
                </div>

                {!trips || trips.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-ink-400 text-sm">No trips yet.</p>
                    <Link href="/trips/new" className="text-accent text-sm hover:text-accent-deep mt-1 inline-block transition-colors">
                      Plan your first trip →
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {trips.map((trip, i) => {
                      const nights = Math.max(
                        1,
                        Math.ceil((new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) / 86400000),
                      );
                      return (
                        <motion.div
                          key={trip.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.28 + i * 0.04 }}
                        >
                          <Link href={`/trips/${trip.id}`}>
                            <div className="rounded-xl px-4 py-3 flex items-center gap-3 border border-ink-900/10 hover:border-ink-900/20 transition-colors group cursor-pointer">
                              <div className="w-8 h-8 rounded-lg bg-ink-100 flex items-center justify-center shrink-0">
                                <Map className="w-3.5 h-3.5 text-ink-400" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-ink-900 truncate">{trip.destination_city}</p>
                                <p className="text-xs font-mono text-ink-400 flex items-center gap-1.5 mt-0.5">
                                  <Calendar className="w-3 h-3" />
                                  {new Date(trip.start_date).toLocaleDateString("en-US", {
                                    month: "short",
                                    day: "numeric",
                                    year: "numeric",
                                  })}
                                  <span className="text-ink-300">·</span>
                                  {nights}n
                                </p>
                              </div>
                              <StatusBadge status={trip.status} className="shrink-0" />
                            </div>
                          </Link>
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </Card>
            </motion.div>
          </div>

          {/* RIGHT COLUMN — memory stats + sign out */}
          <div className="lg:col-span-2 space-y-5">
            {/* ── AI MEMORY STATS GRID ───────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2, duration: 0.45, ease: EASE }}
            >
              <Card padding="sm">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 rounded-lg bg-sunset flex items-center justify-center">
                    <Brain className="w-3.5 h-3.5 text-[#1F1206]" />
                  </div>
                  <h2 className="font-medium text-ink-900 text-sm">AI Memory</h2>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {/* Card 1 — Decisions */}
                  <div className="bg-ink-100 rounded-lg p-4 text-center">
                    <p className="font-mono text-2xl font-medium text-accent tabular-nums">
                      <CountUp target={decisionsLearned} />
                    </p>
                    <p className="text-[11px] text-ink-400 mt-1 leading-tight">
                      Decisions
                      <br />
                      learned
                    </p>
                  </div>

                  {/* Card 2 — Trips */}
                  <div className="bg-ink-100 rounded-lg p-4 text-center">
                    <p className="font-mono text-2xl font-medium text-accent tabular-nums">
                      <CountUp target={trips?.length ?? 0} />
                    </p>
                    <p className="text-[11px] text-ink-400 mt-1 leading-tight">
                      Trips
                      <br />
                      planned
                    </p>
                  </div>

                  {/* Card 3 — Confidence ring */}
                  <div className="bg-ink-100 rounded-lg p-4 flex flex-col items-center gap-2">
                    <div className="relative">
                      <RingProgress value={confidencePct} max={50} size={56} stroke={5} />
                      <span className="absolute inset-0 flex items-center justify-center font-mono text-xs font-medium text-accent">
                        {Math.round((confidencePct / 50) * 100)}%
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-400 text-center leading-tight">
                      Personalisation
                      <br />
                      confidence
                    </p>
                  </div>

                  {/* Card 4 — Learning pulse */}
                  <div className="bg-ink-100 rounded-lg p-4 flex flex-col items-center justify-center gap-2.5">
                    <div className="relative flex items-center justify-center">
                      <div className="absolute w-8 h-8 rounded-full bg-accent/20 animate-ping" />
                      <div className="w-4 h-4 rounded-full bg-accent" />
                    </div>
                    <p className="text-[11px] text-ink-400 text-center leading-tight">
                      AI is learning
                      <br />
                      from you
                    </p>
                  </div>
                </div>

                <p className="text-[11px] text-ink-300 text-center mt-4">Confidence maxes out at 50 decisions. Keep planning!</p>
              </Card>
            </motion.div>

            {/* ── QUICK LINKS ───────────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3, duration: 0.45, ease: EASE }}
            >
              <Card padding="sm">
                <SectionHeader eyebrow="Quick Actions" />
                <div className="space-y-2">
                  <Link href="/trips">
                    <motion.div
                      whileHover={{ x: 3 }}
                      className="flex items-center gap-3 px-4 py-3 rounded-xl border border-ink-900/10 cursor-pointer hover:border-ink-900/20 transition-colors group"
                    >
                      <Map className="w-4 h-4 text-ink-400" />
                      <span className="text-sm text-ink-600 group-hover:text-ink-900 transition-colors">My Trips</span>
                      <ArrowRight className="ml-auto w-3.5 h-3.5 text-ink-300 group-hover:text-ink-600 transition-colors" />
                    </motion.div>
                  </Link>

                  <Link href="/trips/new">
                    <motion.div
                      whileHover={{ x: 3 }}
                      className="flex items-center gap-3 px-4 py-3 rounded-xl border border-ink-900/10 cursor-pointer hover:border-ink-900/20 transition-colors group"
                    >
                      <Zap className="w-4 h-4 text-ink-400" />
                      <span className="text-sm text-ink-600 group-hover:text-ink-900 transition-colors">Plan New Trip</span>
                      <ArrowRight className="ml-auto w-3.5 h-3.5 text-ink-300 group-hover:text-ink-600 transition-colors" />
                    </motion.div>
                  </Link>
                </div>
              </Card>
            </motion.div>

            {/* ── SIGN OUT ──────────────────────────────────────────── */}
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.38, duration: 0.45 }}>
              <Button
                variant="secondary"
                onClick={handleLogout}
                iconLeft={LogOut}
                className="w-full hover:text-danger hover:border-danger/30"
              >
                Sign Out
              </Button>
            </motion.div>
          </div>
        </div>
      </main>
    </div>
  );
}
