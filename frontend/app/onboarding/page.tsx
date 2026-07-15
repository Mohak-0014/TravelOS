"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Compass, ArrowRight, ArrowLeft, Check, Zap, Coffee, Scale, Rocket, Wallet, Gem, type LucideIcon } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { INTERESTS, FOOD_PREFS } from "@/lib/constants";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { slideX } from "@/lib/motion";
import { cn } from "@/lib/ui";

// ── Step config ───────────────────────────────────────────────────────────────

type PaceId = "relaxed" | "moderate" | "packed";
type LuxuryId = "budget" | "mid" | "luxury";

const PACE_OPTIONS: { id: PaceId; label: string; sub: string; icon: LucideIcon }[] = [
  { id: "relaxed", label: "Relaxed", sub: "2–3 activities/day, plenty of downtime", icon: Coffee },
  { id: "moderate", label: "Moderate", sub: "4 activities/day, balanced pace", icon: Scale },
  { id: "packed", label: "Packed", sub: "5–6 activities/day, maximum exploration", icon: Rocket },
];

const LUXURY_OPTIONS: { id: LuxuryId; label: string; sub: string; icon: LucideIcon }[] = [
  { id: "budget", label: "Budget", sub: "Hostels, street food, local transit", icon: Wallet },
  { id: "mid", label: "Mid-range", sub: "3-star hotels, casual restaurants", icon: Scale },
  { id: "luxury", label: "Luxury", sub: "5-star stays, fine dining, private tours", icon: Gem },
];

const TOTAL_STEPS = 4;

function OptionCard({
  icon: Icon,
  label,
  sub,
  selected,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  sub: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-4 p-4 rounded-xl border text-left transition-colors duration-150",
        selected ? "border-accent/50 bg-accent-tint shadow-glow" : "border-ink-900/10 bg-surface hover:border-ink-900/20",
      )}
    >
      <div className={cn("p-2.5 rounded-lg", selected ? "bg-surface-raised" : "bg-ink-100")}>
        <Icon className={cn("w-5 h-5", selected ? "text-accent" : "text-ink-400")} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn("font-medium text-sm", selected ? "text-ink-900" : "text-ink-600")}>{label}</p>
        <p className="text-xs text-ink-400 mt-0.5">{sub}</p>
      </div>
      {selected && (
        <div className="w-5 h-5 rounded-full bg-sunset flex items-center justify-center shrink-0">
          <Check className="w-3 h-3 text-[#1F1206]" />
        </div>
      )}
    </button>
  );
}

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

  function next() {
    setDir(1);
    setStep((s) => s + 1);
  }
  function prev() {
    setDir(-1);
    setStep((s) => s - 1);
  }

  function toggleSet(set: Set<string>, id: string): Set<string> {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
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
        budget_behavior: luxuryTier === "budget" ? "frugal" : luxuryTier === "luxury" ? "splurge" : "balanced",
        walking_tolerance: pace === "packed" ? "high" : pace === "relaxed" ? "low" : "medium",
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

  const canContinue = (step === 0 && pace !== null) || (step === 1 && luxuryTier !== null) || step >= 2;

  return (
    <div className="relative min-h-screen bg-paper flex flex-col items-center justify-center px-4 py-12 overflow-hidden">
      {/* Warm ambient bloom */}
      <div
        className="absolute left-1/2 top-0 -translate-x-1/2 w-[900px] h-[500px] pointer-events-none"
        style={{ background: "radial-gradient(55% 70% at 50% 0%, rgba(255,158,100,0.08) 0%, transparent 70%)" }}
      />
      <div className="relative z-10 w-full max-w-lg">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
          <Badge tone="accent" icon={Compass} className="mb-4">
            Travel DNA setup
          </Badge>
          <h1 className="font-display text-3xl font-medium text-ink-900">Personalize your experience</h1>
          <p className="text-ink-400 text-sm mt-1.5">Your AI agents use this to plan every trip from day&nbsp;one.</p>
        </motion.div>

        {/* Progress */}
        <div className="mb-6">
          <div className="flex justify-between text-xs font-mono text-ink-400 mb-2">
            <span>
              Step {step + 1} of {TOTAL_STEPS}
            </span>
            <span>{Math.round(progress)}%</span>
          </div>
          <ProgressBar value={progress} />
        </div>

        {/* Card */}
        <Card padding="none" className="overflow-hidden" style={{ minHeight: 380 }}>
          <AnimatePresence mode="wait">
            <motion.div key={step} variants={slideX(dir as 1 | -1)} initial="enter" animate="center" exit="exit" className="p-6">
              {/* ── Step 0: Pace ─────────────────────────────── */}
              {step === 0 && (
                <>
                  <h2 className="font-display text-lg font-medium text-ink-900 mb-0.5">How do you like to travel?</h2>
                  <p className="text-xs text-ink-400 mb-5">Sets activities per day in your itinerary.</p>
                  <div className="space-y-3">
                    {PACE_OPTIONS.map((opt) => (
                      <OptionCard key={opt.id} {...opt} selected={pace === opt.id} onClick={() => setPace(opt.id)} />
                    ))}
                  </div>
                </>
              )}

              {/* ── Step 1: Luxury tier ───────────────────────── */}
              {step === 1 && (
                <>
                  <h2 className="font-display text-lg font-medium text-ink-900 mb-0.5">What&apos;s your travel style?</h2>
                  <p className="text-xs text-ink-400 mb-5">Drives hotel tier, dining, and budget split.</p>
                  <div className="space-y-3">
                    {LUXURY_OPTIONS.map((opt) => (
                      <OptionCard key={opt.id} {...opt} selected={luxuryTier === opt.id} onClick={() => setLuxuryTier(opt.id)} />
                    ))}
                  </div>
                </>
              )}

              {/* ── Step 2: Interests ─────────────────────────── */}
              {step === 2 && (
                <>
                  <h2 className="font-display text-lg font-medium text-ink-900 mb-0.5">What do you love?</h2>
                  <p className="text-xs text-ink-400 mb-5">Pick as many as you like — we&apos;ll prioritize these.</p>
                  <div className="grid grid-cols-2 gap-2">
                    {INTERESTS.map((opt) => (
                      <Chip
                        key={opt.id}
                        icon={opt.icon}
                        selected={interests.has(opt.id)}
                        onClick={() => setInterests(toggleSet(interests, opt.id))}
                        className="w-full justify-start"
                      >
                        {opt.label}
                      </Chip>
                    ))}
                  </div>
                </>
              )}

              {/* ── Step 3: Food prefs ────────────────────────── */}
              {step === 3 && (
                <>
                  <h2 className="font-display text-lg font-medium text-ink-900 mb-0.5">Food preferences</h2>
                  <p className="text-xs text-ink-400 mb-5">We&apos;ll factor these into restaurant picks.</p>
                  <div className="grid grid-cols-2 gap-2">
                    {FOOD_PREFS.map((opt) => (
                      <Chip
                        key={opt.id}
                        icon={opt.icon}
                        selected={foodPrefs.has(opt.id)}
                        onClick={() => setFoodPrefs(toggleSet(foodPrefs, opt.id))}
                        className="w-full justify-start"
                      >
                        {opt.label}
                      </Chip>
                    ))}
                  </div>
                  {saveError && <p className="text-xs text-danger mt-4 text-center">{saveError}</p>}
                </>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Footer */}
          <div className="px-6 pb-6 flex items-center justify-between gap-3">
            {step > 0 ? (
              <button onClick={prev} className="flex items-center gap-1.5 text-sm text-ink-400 hover:text-ink-900 transition-colors">
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            ) : (
              <button onClick={() => router.push("/trips")} className="text-sm text-ink-300 hover:text-ink-600 transition-colors">
                Skip for now
              </button>
            )}

            {step < TOTAL_STEPS - 1 ? (
              <Button onClick={next} disabled={!canContinue} iconRight={ArrowRight}>
                Continue
              </Button>
            ) : (
              <Button onClick={handleFinish} loading={saving} iconLeft={Zap}>
                {saving ? "Saving…" : "Start planning"}
              </Button>
            )}
          </div>
        </Card>

        {/* Step dots */}
        <div className="flex justify-center gap-2 mt-5">
          {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
            <motion.div
              key={i}
              animate={{
                width: i === step ? 20 : 6,
                backgroundColor: i <= step ? "#FF9E64" : "rgba(255,255,255,0.14)",
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
