"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Compass, ArrowRight, ArrowLeft, Check, Loader2,
  Zap, Coffee, Scale, Rocket, Wallet, Gem,
  Landmark, Mountain, Utensils, Leaf, Moon,
  Palette, BookOpen, Heart,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import dynamic from "next/dynamic";

const StarField = dynamic(() => import("@/components/3d/StarField"), { ssr: false });

// ── Step config ───────────────────────────────────────────────────────────────

type PaceId = "relaxed" | "moderate" | "packed";
type LuxuryId = "budget" | "mid" | "luxury";

const PACE_OPTIONS: { id: PaceId; label: string; sub: string; icon: LucideIcon; color: string }[] = [
  {
    id: "relaxed",
    label: "Relaxed",
    sub: "2–3 activities/day, plenty of downtime",
    icon: Coffee,
    color: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  },
  {
    id: "moderate",
    label: "Moderate",
    sub: "4 activities/day, balanced pace",
    icon: Scale,
    color: "border-electric-500/40 bg-electric-500/10 text-electric-400",
  },
  {
    id: "packed",
    label: "Packed",
    sub: "5–6 activities/day, maximum exploration",
    icon: Rocket,
    color: "border-coral-500/40 bg-coral-500/10 text-coral-400",
  },
];

const LUXURY_OPTIONS: { id: LuxuryId; label: string; sub: string; icon: LucideIcon; color: string }[] = [
  {
    id: "budget",
    label: "Budget",
    sub: "Hostels, street food, local transit",
    icon: Wallet,
    color: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  },
  {
    id: "mid",
    label: "Mid-range",
    sub: "3-star hotels, casual restaurants",
    icon: Scale,
    color: "border-electric-500/40 bg-electric-500/10 text-electric-400",
  },
  {
    id: "luxury",
    label: "Luxury",
    sub: "5-star stays, fine dining, private tours",
    icon: Gem,
    color: "border-yellow-500/40 bg-yellow-500/10 text-yellow-400",
  },
];

const INTERESTS: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "culture", label: "Culture", icon: Landmark },
  { id: "adventure", label: "Adventure", icon: Mountain },
  { id: "food", label: "Food & Drink", icon: Utensils },
  { id: "nature", label: "Nature", icon: Leaf },
  { id: "nightlife", label: "Nightlife", icon: Moon },
  { id: "art", label: "Art & Museums", icon: Palette },
  { id: "history", label: "History", icon: BookOpen },
  { id: "wellness", label: "Wellness", icon: Heart },
];

const FOOD_PREFS: { id: string; label: string; emoji: string }[] = [
  { id: "local_cuisine", label: "Local Cuisine", emoji: "🌍" },
  { id: "street_food", label: "Street Food", emoji: "🌮" },
  { id: "fine_dining", label: "Fine Dining", emoji: "🍽️" },
  { id: "vegetarian", label: "Vegetarian", emoji: "🥦" },
  { id: "vegan", label: "Vegan", emoji: "🌱" },
  { id: "seafood", label: "Seafood", emoji: "🦞" },
  { id: "halal", label: "Halal", emoji: "☪️" },
  { id: "kosher", label: "Kosher", emoji: "✡️" },
];

const TOTAL_STEPS = 4;

const slideVariants = {
  enter: (dir: number) => ({ x: dir * 60, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir: number) => ({ x: dir * -60, opacity: 0 }),
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const { token, _hasHydrated } = useAuthStore();

  const [step, setStep] = useState(0);
  const [dir, setDir] = useState(1);
  const [pace, setPace] = useState<PaceId | null>(null);
  const [luxuryTier, setLuxuryTier] = useState<LuxuryId | null>(null);
  const [interests, setInterests] = useState<Set<string>>(new Set());
  const [foodPrefs, setFoodPrefs] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (_hasHydrated && !token) router.replace("/login");
  }, [_hasHydrated, token, router]);

  const progress = ((step + 1) / TOTAL_STEPS) * 100;

  function next() { setDir(1); setStep((s) => s + 1); }
  function prev() { setDir(-1); setStep((s) => s - 1); }

  function toggleSet(set: Set<string>, id: string): Set<string> {
    const next = new Set(set);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  }

  async function handleFinish() {
    setSaving(true);
    setSaveError(null);
    try {
      await api.put("/api/v1/preferences", {
        pace,
        luxury_tier: luxuryTier,
        interests: Array.from(interests),
        food_prefs: Array.from(foodPrefs),
        budget_behavior:
          luxuryTier === "budget" ? "frugal" : luxuryTier === "luxury" ? "splurge" : "balanced",
        walking_tolerance:
          pace === "packed" ? "high" : pace === "relaxed" ? "low" : "medium",
      });
      router.push("/trips");
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.detail as { message?: string } | null;
        setSaveError(d?.message ?? `Error ${err.status}`);
      } else {
        setSaveError("Could not save. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  const canContinue =
    (step === 0 && pace !== null) ||
    (step === 1 && luxuryTier !== null) ||
    step >= 2;

  return (
    <div className="relative min-h-screen bg-space-900 flex flex-col items-center justify-center overflow-hidden px-4 py-12">
      <StarField />

      {/* Glows */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-electric-500/8 blur-3xl animate-float-slow" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-purple-600/8 blur-3xl animate-float-medium" />
      </div>

      <div className="relative z-10 w-full max-w-lg">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <div className="inline-flex items-center gap-2 text-electric-400 bg-electric-500/10 border border-electric-500/20 px-4 py-1.5 rounded-full text-xs font-semibold mb-4 uppercase tracking-wider">
            <Compass className="w-3.5 h-3.5" />
            Travel DNA setup
          </div>
          <h1 className="text-2xl font-bold text-white">Personalize your experience</h1>
          <p className="text-slate-500 text-sm mt-1.5">
            Your AI agents use this to plan every trip from day&nbsp;one.
          </p>
        </motion.div>

        {/* Progress */}
        <div className="mb-6">
          <div className="flex justify-between text-xs text-slate-600 mb-2">
            <span>Step {step + 1} of {TOTAL_STEPS}</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="h-1 rounded-full bg-white/5 overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-electric-gradient"
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4, ease: "easeInOut" }}
            />
          </div>
        </div>

        {/* Card */}
        <div className="glass-card overflow-hidden" style={{ minHeight: 380 }}>
          <AnimatePresence mode="wait" custom={dir}>
            <motion.div
              key={step}
              custom={dir}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
              className="p-6"
            >
              {/* ── Step 0: Pace ─────────────────────────────── */}
              {step === 0 && (
                <>
                  <h2 className="text-base font-bold text-white mb-0.5">How do you like to travel?</h2>
                  <p className="text-xs text-slate-500 mb-5">Sets activities per day in your itinerary.</p>
                  <div className="space-y-3">
                    {PACE_OPTIONS.map((opt) => {
                      const Icon = opt.icon;
                      const selected = pace === opt.id;
                      return (
                        <motion.button
                          key={opt.id}
                          onClick={() => setPace(opt.id)}
                          whileHover={{ scale: 1.01 }}
                          whileTap={{ scale: 0.98 }}
                          className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all text-left ${
                            selected
                              ? opt.color
                              : "border-white/8 bg-white/3 hover:bg-white/6 hover:border-white/15"
                          }`}
                        >
                          <div className={`p-2.5 rounded-xl ${selected ? "bg-black/20" : "bg-white/5"}`}>
                            <Icon className={`w-5 h-5 ${selected ? "" : "text-slate-400"}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`font-semibold text-sm ${selected ? "text-white" : "text-slate-300"}`}>{opt.label}</p>
                            <p className="text-xs text-slate-500 mt-0.5">{opt.sub}</p>
                          </div>
                          {selected && (
                            <div className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                              <Check className="w-3 h-3 text-white" />
                            </div>
                          )}
                        </motion.button>
                      );
                    })}
                  </div>
                </>
              )}

              {/* ── Step 1: Luxury tier ───────────────────────── */}
              {step === 1 && (
                <>
                  <h2 className="text-base font-bold text-white mb-0.5">What&apos;s your travel style?</h2>
                  <p className="text-xs text-slate-500 mb-5">Drives hotel tier, dining, and budget split.</p>
                  <div className="space-y-3">
                    {LUXURY_OPTIONS.map((opt) => {
                      const Icon = opt.icon;
                      const selected = luxuryTier === opt.id;
                      return (
                        <motion.button
                          key={opt.id}
                          onClick={() => setLuxuryTier(opt.id)}
                          whileHover={{ scale: 1.01 }}
                          whileTap={{ scale: 0.98 }}
                          className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all text-left ${
                            selected
                              ? opt.color
                              : "border-white/8 bg-white/3 hover:bg-white/6 hover:border-white/15"
                          }`}
                        >
                          <div className={`p-2.5 rounded-xl ${selected ? "bg-black/20" : "bg-white/5"}`}>
                            <Icon className={`w-5 h-5 ${selected ? "" : "text-slate-400"}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`font-semibold text-sm ${selected ? "text-white" : "text-slate-300"}`}>{opt.label}</p>
                            <p className="text-xs text-slate-500 mt-0.5">{opt.sub}</p>
                          </div>
                          {selected && (
                            <div className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                              <Check className="w-3 h-3 text-white" />
                            </div>
                          )}
                        </motion.button>
                      );
                    })}
                  </div>
                </>
              )}

              {/* ── Step 2: Interests ─────────────────────────── */}
              {step === 2 && (
                <>
                  <h2 className="text-base font-bold text-white mb-0.5">What do you love?</h2>
                  <p className="text-xs text-slate-500 mb-5">Pick as many as you like — we&apos;ll prioritize these.</p>
                  <div className="grid grid-cols-2 gap-2">
                    {INTERESTS.map((opt) => {
                      const Icon = opt.icon;
                      const selected = interests.has(opt.id);
                      return (
                        <motion.button
                          key={opt.id}
                          onClick={() => setInterests(toggleSet(interests, opt.id))}
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.97 }}
                          className={`flex items-center gap-2.5 p-3 rounded-xl border transition-all text-left ${
                            selected
                              ? "border-electric-500/50 bg-electric-500/15 text-white"
                              : "border-white/8 bg-white/3 text-slate-400 hover:bg-white/6 hover:border-white/15"
                          }`}
                        >
                          <Icon className={`w-4 h-4 shrink-0 ${selected ? "text-electric-400" : ""}`} />
                          <span className="text-sm font-medium">{opt.label}</span>
                          {selected && <Check className="w-3 h-3 text-electric-400 ml-auto shrink-0" />}
                        </motion.button>
                      );
                    })}
                  </div>
                </>
              )}

              {/* ── Step 3: Food prefs ────────────────────────── */}
              {step === 3 && (
                <>
                  <h2 className="text-base font-bold text-white mb-0.5">Food preferences</h2>
                  <p className="text-xs text-slate-500 mb-5">We&apos;ll factor these into restaurant picks.</p>
                  <div className="grid grid-cols-2 gap-2">
                    {FOOD_PREFS.map((opt) => {
                      const selected = foodPrefs.has(opt.id);
                      return (
                        <motion.button
                          key={opt.id}
                          onClick={() => setFoodPrefs(toggleSet(foodPrefs, opt.id))}
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.97 }}
                          className={`flex items-center gap-2.5 p-3 rounded-xl border transition-all text-left ${
                            selected
                              ? "border-yellow-500/50 bg-yellow-500/10 text-white"
                              : "border-white/8 bg-white/3 text-slate-400 hover:bg-white/6 hover:border-white/15"
                          }`}
                        >
                          <span className="text-base shrink-0">{opt.emoji}</span>
                          <span className="text-sm font-medium">{opt.label}</span>
                          {selected && <Check className="w-3 h-3 text-yellow-400 ml-auto shrink-0" />}
                        </motion.button>
                      );
                    })}
                  </div>
                  {saveError && (
                    <p className="text-xs text-red-400 mt-4 text-center">{saveError}</p>
                  )}
                </>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Footer */}
          <div className="px-6 pb-6 flex items-center justify-between gap-3">
            {step > 0 ? (
              <button
                onClick={prev}
                className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            ) : (
              <button
                onClick={() => router.push("/trips")}
                className="text-sm text-slate-600 hover:text-slate-400 transition-colors"
              >
                Skip for now
              </button>
            )}

            {step < TOTAL_STEPS - 1 ? (
              <motion.button
                onClick={next}
                disabled={!canContinue}
                whileHover={canContinue ? { scale: 1.02 } : {}}
                whileTap={canContinue ? { scale: 0.97 } : {}}
                className="flex items-center gap-2 bg-electric-gradient text-white text-sm font-semibold px-5 py-2.5 rounded-xl shadow-electric disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
              >
                Continue
                <ArrowRight className="w-4 h-4" />
              </motion.button>
            ) : (
              <motion.button
                onClick={handleFinish}
                disabled={saving}
                whileHover={!saving ? { scale: 1.02 } : {}}
                whileTap={!saving ? { scale: 0.97 } : {}}
                className="flex items-center gap-2 bg-electric-gradient text-white text-sm font-semibold px-5 py-2.5 rounded-xl shadow-electric disabled:opacity-60 transition-opacity"
              >
                {saving ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</>
                ) : (
                  <><Zap className="w-4 h-4" /> Start planning</>
                )}
              </motion.button>
            )}
          </div>
        </div>

        {/* Step dots */}
        <div className="flex justify-center gap-2 mt-5">
          {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
            <motion.div
              key={i}
              animate={{
                width: i === step ? 20 : 6,
                backgroundColor:
                  i === step ? "#3b82f6" : i < step ? "#60a5fa" : "rgba(255,255,255,0.12)",
              }}
              transition={{ duration: 0.3 }}
              className="h-1.5 rounded-full"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
