"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  MapPin,
  Calendar,
  Users,
  IndianRupee,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Globe2,
  CheckCircle2,
  Zap,
  PlaneTakeoff,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { TripOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { flightOriginKey } from "@/lib/constants";
import NavBar from "@/components/ui/NavBar";
import { Card } from "@/components/ui/Card";
import { Chip } from "@/components/ui/Chip";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EASE } from "@/lib/motion";

// ── Constants ─────────────────────────────────────────────────────────────────

const QUICK_DESTINATIONS = ["Tokyo", "Rome", "Paris", "Bali", "New York", "Barcelona"];

const BUDGET_CURRENCY = "INR";

const PIPELINE_STEPS = [
  { icon: Sparkles, text: "Travel Style agent reads your preferences" },
  { icon: MapPin, text: "Itinerary Planner clusters attractions into walking zones" },
  { icon: Globe2, text: "Hotel Agent finds options matching your budget tier" },
  { icon: IndianRupee, text: "Budget Optimizer checks spend vs. your budget" },
  { icon: Zap, text: "Events Agent checks what's on during your trip" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function calcNights(start: string, end: string): number | null {
  if (!start || !end) return null;
  const diff = (new Date(end).getTime() - new Date(start).getTime()) / 86400000;
  return diff > 0 ? Math.round(diff) : null;
}

function calcBudgetTier(budget: string, travelers: number, start: string, end: string): string | null {
  const nights = calcNights(start, end);
  const total = parseFloat(budget);
  if (!budget || isNaN(total) || !nights || nights <= 0 || travelers <= 0) return null;
  const perPersonPerDay = total / travelers / nights;
  if (perPersonPerDay < 4000) return "Budget Explorer";
  if (perPersonPerDay <= 12000) return "Balanced Traveler";
  return "Luxury Seeker";
}

function tierTone(tier: string | null): "success" | "warning" | "info" | "neutral" {
  if (tier === "Budget Explorer") return "success";
  if (tier === "Balanced Traveler") return "warning";
  if (tier === "Luxury Seeker") return "info";
  return "neutral";
}

// ── Step animation variants ───────────────────────────────────────────────────

const stepVariants = (direction: number) => ({
  initial: { opacity: 0, x: direction * 50 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.35, ease: EASE } },
  exit: { opacity: 0, x: -direction * 50, transition: { duration: 0.25, ease: EASE } },
});

// ── Step indicator (numbered circles + connecting track) ─────────────────────

function StepIndicator({ step, total }: { step: number; total: number }) {
  const labels = ["Destination", "Dates", "Travelers & Budget", "Launch"];
  return (
    <div className="w-full max-w-xl mx-auto mb-10">
      <div className="flex items-start justify-between mb-2">
        {labels.map((label, i) => {
          const done = i < step;
          const current = i === step;
          return (
            <div key={label} className="flex flex-col items-center gap-1.5">
              <motion.div
                animate={{ scale: current ? 1.15 : 1 }}
                transition={{ duration: 0.3 }}
                className={`w-8 h-8 rounded-full border-2 flex items-center justify-center ${
                  done ? "bg-sunset border-accent" : current ? "bg-accent-tint border-accent" : "bg-surface border-ink-900/10"
                }`}
              >
                {done ? (
                  <CheckCircle2 className="w-4 h-4 text-[#1F1206]" />
                ) : (
                  <span className={`text-xs font-mono font-medium ${current ? "text-accent" : "text-ink-300"}`}>{i + 1}</span>
                )}
              </motion.div>
              <span
                className={`text-xs font-medium hidden sm:block text-center max-w-[72px] leading-tight ${
                  current ? "text-accent" : done ? "text-ink-600" : "text-ink-300"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Connecting track */}
      <div className="relative h-px bg-ink-900/10 rounded-full mx-4 mt-1 hidden sm:block">
        <motion.div
          className="absolute left-0 top-0 h-full rounded-full bg-sunset"
          animate={{ width: `${(step / (total - 1)) * 100}%` }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
        />
      </div>
    </div>
  );
}

// ── Step 1 — Destination ──────────────────────────────────────────────────────

function StepDestination({
  destination,
  setDestination,
  onNext,
}: {
  destination: string;
  setDestination: (v: string) => void;
  onNext: () => void;
}) {
  return (
    <div className="text-center">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
        <div className="inline-flex w-14 h-14 rounded-2xl bg-sunset items-center justify-center mb-5 shadow-glow">
          <Globe2 className="w-7 h-7 text-[#1F1206]" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="font-mono text-ink-400 text-xs font-medium uppercase tracking-wider mb-2"
      >
        Step 1 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="font-display text-5xl font-medium text-ink-900 mb-10"
      >
        Where to?
      </motion.h1>

      {/* Big destination input */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="relative mb-8">
        <MapPin className="absolute left-0 top-1/2 -translate-y-1/2 w-6 h-6 text-accent pointer-events-none" />
        <input
          type="text"
          autoFocus
          placeholder="Paris, Tokyo, Bali..."
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && destination.trim()) onNext();
          }}
          className="w-full pl-10 pr-4 py-4 text-4xl font-light bg-transparent border-b-2 border-ink-900/10 focus:border-accent focus:outline-none text-ink-900 placeholder-ink-300 transition-colors duration-300"
          style={{ caretColor: "#FF9E64" }}
        />
      </motion.div>

      {/* Quick-pick pills */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mb-10">
        <p className="font-mono text-xs text-ink-300 uppercase tracking-wider mb-4">Popular destinations</p>
        <div className="flex flex-wrap justify-center gap-2">
          {QUICK_DESTINATIONS.map((label, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.35 + i * 0.05 }}
            >
              <Chip selected={destination === label} onClick={() => setDestination(label)}>
                {label}
              </Chip>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Next button */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
        <Button onClick={onNext} disabled={!destination.trim()} iconRight={ArrowRight} className="mx-auto">
          Continue
        </Button>
      </motion.div>
    </div>
  );
}

// ── Step 2 — Dates ────────────────────────────────────────────────────────────

function StepDates({
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  onNext,
  onBack,
}: {
  startDate: string;
  setStartDate: (v: string) => void;
  endDate: string;
  setEndDate: (v: string) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const nights = calcNights(startDate, endDate);
  const canNext = !!startDate && !!endDate && (nights ?? 0) > 0;
  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="text-center">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="inline-flex w-14 h-14 rounded-2xl bg-sunset items-center justify-center mb-5 shadow-glow">
          <Calendar className="w-7 h-7 text-[#1F1206]" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="font-mono text-ink-400 text-xs font-medium uppercase tracking-wider mb-2"
      >
        Step 2 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="font-display text-4xl font-medium text-ink-900 mb-10"
      >
        When are you going?
      </motion.h1>

      {/* Date pickers */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6 text-left"
      >
        <div>
          <label className="block font-mono text-xs font-medium text-ink-400 uppercase tracking-wider mb-2">Departure</label>
          <Input
            type="date"
            value={startDate}
            min={today}
            onChange={(e) => {
              setStartDate(e.target.value);
              if (endDate && e.target.value >= endDate) setEndDate("");
            }}
            className="cursor-pointer"
          />
        </div>
        <div>
          <label className="block font-mono text-xs font-medium text-ink-400 uppercase tracking-wider mb-2">Return</label>
          <Input
            type="date"
            value={endDate}
            min={startDate || today}
            onChange={(e) => setEndDate(e.target.value)}
            className="cursor-pointer"
          />
        </div>
      </motion.div>

      {/* Nights badge */}
      <AnimatePresence mode="wait">
        {nights !== null && nights > 0 && (
          <motion.div
            key="nights-badge"
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            className="inline-block mb-6"
          >
            <Badge tone="accent" icon={Calendar}>
              {nights} night{nights !== 1 ? "s" : ""}
            </Badge>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Travel tip */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}>
        <Card padding="sm" className="mb-8 flex items-start gap-3 text-left">
          <Zap className="w-4 h-4 text-accent shrink-0 mt-0.5" />
          <p className="text-sm text-ink-600 leading-relaxed">
            <span className="text-ink-900 font-medium">Planning ahead?</span> We&rsquo;ll automatically fetch weather forecasts for your
            travel window and adapt your itinerary for any adverse conditions.
          </p>
        </Card>
      </motion.div>

      {/* Navigation */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="flex items-center justify-between"
      >
        <Button variant="ghost" onClick={onBack} iconLeft={ArrowLeft}>
          Back
        </Button>
        <Button onClick={onNext} disabled={!canNext} iconRight={ArrowRight}>
          Continue
        </Button>
      </motion.div>
    </div>
  );
}

// ── Step 3 — Travelers + Budget ───────────────────────────────────────────────

function StepTravelersBudget({
  travelers,
  setTravelers,
  budget,
  setBudget,
  flightOrigin,
  setFlightOrigin,
  startDate,
  endDate,
  onNext,
  onBack,
}: {
  travelers: number;
  setTravelers: (v: number) => void;
  budget: string;
  setBudget: (v: string) => void;
  currency: string;
  setCurrency: (v: string) => void;
  flightOrigin: string;
  setFlightOrigin: (v: string) => void;
  startDate: string;
  endDate: string;
  onNext: () => void;
  onBack: () => void;
}) {
  const tier = calcBudgetTier(budget, travelers, startDate, endDate);

  return (
    <div className="text-center">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="inline-flex w-14 h-14 rounded-2xl bg-sunset items-center justify-center mb-5 shadow-glow">
          <Users className="w-7 h-7 text-[#1F1206]" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="font-mono text-ink-400 text-xs font-medium uppercase tracking-wider mb-2"
      >
        Step 3 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="font-display text-4xl font-medium text-ink-900 mb-10"
      >
        Who&rsquo;s coming?
      </motion.h1>

      {/* Traveler count */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
        <Card className="mb-5 text-left">
          <p className="font-mono text-xs font-medium text-ink-400 uppercase tracking-wider mb-5">Number of travelers</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-5">
              <button
                onClick={() => setTravelers(Math.max(1, travelers - 1))}
                disabled={travelers <= 1}
                className="w-11 h-11 rounded-full border border-ink-900/10 text-ink-600 text-xl font-light flex items-center justify-center hover:border-accent/40 hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                −
              </button>

              <div className="text-center min-w-[4rem]">
                <motion.p
                  key={travelers}
                  initial={{ scale: 0.7, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="font-mono text-5xl font-medium text-ink-900"
                >
                  {travelers}
                </motion.p>
                <p className="text-xs text-ink-400 mt-1">{travelers === 1 ? "solo traveler" : "travelers"}</p>
              </div>

              <button
                onClick={() => setTravelers(Math.min(12, travelers + 1))}
                disabled={travelers >= 12}
                className="w-11 h-11 rounded-full border border-ink-900/10 text-ink-600 text-xl font-light flex items-center justify-center hover:border-accent/40 hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                +
              </button>
            </div>

            {/* Pax visual dots */}
            <div className="hidden sm:flex flex-wrap gap-1.5 max-w-[120px] justify-end">
              {Array.from({ length: Math.min(travelers, 12) }).map((_, i) => (
                <motion.div
                  key={i}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: i * 0.04 }}
                  className="w-4 h-4 rounded-full bg-accent/60"
                />
              ))}
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Budget */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card className="mb-8 text-left">
          <p className="font-mono text-xs font-medium text-ink-400 uppercase tracking-wider mb-5">
            Total trip budget <span className="normal-case text-ink-300 font-normal">(optional)</span>
          </p>
          <div className="flex gap-3">
            <Input
              icon={IndianRupee}
              type="number"
              min="0"
              placeholder="150000"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="flex-1"
            />
            <div className="h-10 w-20 shrink-0 rounded-lg border border-ink-900/10 bg-ink-100 flex items-center justify-center font-mono text-sm font-medium text-ink-600 select-none">
              INR
            </div>
          </div>

          {/* Budget tier badge */}
          <AnimatePresence mode="wait">
            {tier && (
              <motion.div
                key={tier}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="inline-block mt-4"
              >
                <Badge tone={tierTone(tier)} icon={Sparkles}>
                  {tier}
                </Badge>
              </motion.div>
            )}
          </AnimatePresence>
        </Card>
      </motion.div>

      {/* Departure airport */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
        <Card className="mb-8 text-left">
          <p className="font-mono text-xs font-medium text-ink-400 uppercase tracking-wider mb-5">
            Departure Airport <span className="normal-case text-ink-300 font-normal">(optional — for flight budget)</span>
          </p>
          <Input
            icon={PlaneTakeoff}
            type="text"
            placeholder="IATA code — DEL, JFK, LHR…"
            value={flightOrigin}
            onChange={(e) =>
              setFlightOrigin(
                e.target.value
                  .toUpperCase()
                  .replace(/[^A-Z]/g, "")
                  .slice(0, 3),
              )
            }
            maxLength={3}
            className="uppercase tracking-widest font-mono placeholder:normal-case placeholder:tracking-normal placeholder:font-sans"
          />
          <p className="text-xs text-ink-400 mt-3 flex items-start gap-1.5">
            <Zap className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
            Flight costs will be fetched and factored into your budget breakdown.
          </p>
        </Card>
      </motion.div>

      {/* Navigation */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="flex items-center justify-between"
      >
        <Button variant="ghost" onClick={onBack} iconLeft={ArrowLeft}>
          Back
        </Button>
        <Button onClick={onNext} iconRight={ArrowRight}>
          Continue
        </Button>
      </motion.div>
    </div>
  );
}

// ── Step 4 — Launch ───────────────────────────────────────────────────────────

function StepLaunch({
  destination,
  startDate,
  endDate,
  travelers,
  budget,
  currency,
  flightOrigin,
  onBack,
  onSubmit,
  isSubmitting,
  error,
}: {
  destination: string;
  startDate: string;
  endDate: string;
  travelers: number;
  budget: string;
  currency: string;
  flightOrigin: string;
  onBack: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  error: string | null;
}) {
  const nights = calcNights(startDate, endDate);
  const tier = calcBudgetTier(budget, travelers, startDate, endDate);

  const formatDate = (d: string) =>
    d ? new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

  return (
    <div className="text-center">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="inline-flex w-14 h-14 rounded-2xl bg-sunset items-center justify-center mb-5 shadow-glow">
          <Sparkles className="w-7 h-7 text-[#1F1206]" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="font-mono text-ink-400 text-xs font-medium uppercase tracking-wider mb-2"
      >
        Step 4 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="font-display text-4xl font-medium text-ink-900 mb-8"
      >
        Ready to launch?
      </motion.h1>

      {/* Summary card */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
        <Card className="mb-5 text-left">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle2 className="w-4 h-4 text-success" />
            <span className="font-mono text-xs font-medium text-ink-400 uppercase tracking-wider">Trip summary</span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-ink-400 mb-1 flex items-center gap-1">
                <MapPin className="w-3 h-3" /> Destination
              </p>
              <p className="text-xl font-medium text-ink-900">{destination}</p>
            </div>

            <div>
              <p className="text-xs text-ink-400 mb-1 flex items-center gap-1">
                <Users className="w-3 h-3" /> Travelers
              </p>
              <p className="text-xl font-medium text-ink-900">
                {travelers} <span className="text-sm font-normal text-ink-400">{travelers === 1 ? "person" : "people"}</span>
              </p>
            </div>

            <div>
              <p className="text-xs text-ink-400 mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> Dates
              </p>
              <p className="text-sm font-medium text-ink-900 font-mono">
                {formatDate(startDate)} – {formatDate(endDate)}
              </p>
              {nights !== null && <p className="text-xs text-ink-400 mt-0.5">{nights} nights</p>}
            </div>

            <div>
              <p className="text-xs text-ink-400 mb-1 flex items-center gap-1">
                <IndianRupee className="w-3 h-3" /> Budget
              </p>
              {budget ? (
                <>
                  <p className="text-sm font-medium text-ink-900 font-mono">
                    {currency} {parseFloat(budget).toLocaleString()}
                  </p>
                  {tier && (
                    <Badge tone={tierTone(tier)} className="mt-1">
                      {tier}
                    </Badge>
                  )}
                </>
              ) : (
                <p className="text-sm text-ink-300 italic">Not set</p>
              )}
            </div>

            <div>
              <p className="text-xs text-ink-400 mb-1 flex items-center gap-1">
                <PlaneTakeoff className="w-3 h-3" /> Flying from
              </p>
              {flightOrigin.length === 3 ? (
                <p className="text-xl font-medium text-ink-900 font-mono tracking-widest">{flightOrigin}</p>
              ) : (
                <p className="text-sm text-ink-300 italic">Not set</p>
              )}
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Agent pipeline */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card className="mb-6 text-left">
          <p className="font-mono text-xs font-medium text-ink-400 uppercase tracking-wider mb-4">
            What happens when you click Start Planning
          </p>
          <div className="space-y-3">
            {PIPELINE_STEPS.map(({ icon: Icon, text }, i) => (
              <motion.div
                key={text}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.25 + i * 0.07 }}
                className="flex items-center gap-3"
              >
                <div className="w-7 h-7 rounded-lg bg-accent-tint flex items-center justify-center shrink-0">
                  <Icon className="w-3.5 h-3.5 text-accent" />
                </div>
                <p className="text-sm text-ink-600 leading-snug">{text}</p>
              </motion.div>
            ))}
          </div>
        </Card>
      </motion.div>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="mb-5 px-4 py-3 rounded-lg bg-danger-tint text-danger text-sm text-left"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Navigation */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="flex items-center justify-between"
      >
        <Button variant="ghost" onClick={onBack} disabled={isSubmitting} iconLeft={ArrowLeft}>
          Back
        </Button>

        <Button onClick={onSubmit} loading={isSubmitting} iconLeft={Sparkles} size="lg">
          {isSubmitting ? "Building your trip…" : "Start Planning"}
        </Button>
      </motion.div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NewTripPage() {
  const router = useRouter();
  const { token, _hasHydrated } = useAuthStore();

  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);

  // Form state
  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [travelers, setTravelers] = useState(1);
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState(BUDGET_CURRENCY);
  const [flightOrigin, setFlightOrigin] = useState("");

  // Submit state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auth guard
  useEffect(() => {
    if (_hasHydrated && !token) router.replace("/login");
  }, [_hasHydrated, token, router]);

  if (!_hasHydrated) return null;

  function goNext() {
    setDirection(1);
    setStep((s) => s + 1);
  }

  function goBack() {
    setDirection(-1);
    setStep((s) => s - 1);
  }

  async function handleSubmit() {
    setError(null);
    setIsSubmitting(true);
    try {
      const trip = await api.post<TripOut>("/api/v1/trips", {
        title: `${destination} Trip`,
        destination_city: destination,
        destination_country: "",
        start_date: startDate,
        end_date: endDate,
        num_travelers: travelers,
        budget_total: budget ? parseFloat(budget) : null,
        budget_currency: currency,
        flight_origin: flightOrigin.trim().length === 3 ? flightOrigin.trim().toUpperCase() : null,
      });
      if (flightOrigin.trim().length === 3) {
        sessionStorage.setItem(flightOriginKey(trip.id), flightOrigin.trim().toUpperCase());
      }
      router.push(`/trips/${trip.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { detail?: string; message?: string } | string | null;
        const msg = typeof detail === "string" ? detail : (detail?.detail ?? detail?.message ?? "Something went wrong. Please try again.");
        setError(msg);
      } else {
        setError("Something went wrong. Please try again.");
      }
      setIsSubmitting(false);
    }
  }

  const variants = stepVariants(direction);

  return (
    <div className="relative min-h-screen bg-paper overflow-x-hidden">
      <NavBar />

      <main className="relative z-10 min-h-screen flex flex-col items-center justify-center px-4 pt-20 pb-16">
        <div className="w-full max-w-xl">
          {/* Progress indicator */}
          <StepIndicator step={step} total={4} />

          {/* Step card */}
          <Card className="p-8 sm:p-10">
            <AnimatePresence mode="wait" initial={false}>
              {step === 0 && (
                <motion.div key="step-0" variants={variants} initial="initial" animate="animate" exit="exit">
                  <StepDestination destination={destination} setDestination={setDestination} onNext={goNext} />
                </motion.div>
              )}

              {step === 1 && (
                <motion.div key="step-1" variants={variants} initial="initial" animate="animate" exit="exit">
                  <StepDates
                    startDate={startDate}
                    setStartDate={setStartDate}
                    endDate={endDate}
                    setEndDate={setEndDate}
                    onNext={goNext}
                    onBack={goBack}
                  />
                </motion.div>
              )}

              {step === 2 && (
                <motion.div key="step-2" variants={variants} initial="initial" animate="animate" exit="exit">
                  <StepTravelersBudget
                    travelers={travelers}
                    setTravelers={setTravelers}
                    budget={budget}
                    setBudget={setBudget}
                    currency={currency}
                    setCurrency={setCurrency}
                    flightOrigin={flightOrigin}
                    setFlightOrigin={setFlightOrigin}
                    startDate={startDate}
                    endDate={endDate}
                    onNext={goNext}
                    onBack={goBack}
                  />
                </motion.div>
              )}

              {step === 3 && (
                <motion.div key="step-3" variants={variants} initial="initial" animate="animate" exit="exit">
                  <StepLaunch
                    destination={destination}
                    startDate={startDate}
                    endDate={endDate}
                    travelers={travelers}
                    budget={budget}
                    currency={currency}
                    flightOrigin={flightOrigin}
                    onBack={goBack}
                    onSubmit={handleSubmit}
                    isSubmitting={isSubmitting}
                    error={error}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </Card>

          {/* Footer hint */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="text-center text-xs text-ink-300 mt-6"
          >
            Powered by multi-agent AI — hotels, weather, events, and budget auto-optimized.
          </motion.p>
        </div>
      </main>
    </div>
  );
}
