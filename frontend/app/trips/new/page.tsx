"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  MapPin,
  Calendar,
  Users,
  DollarSign,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Globe2,
  CheckCircle2,
  Zap,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { TripOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import NavBar from "@/components/ui/NavBar";

// ── Constants ─────────────────────────────────────────────────────────────────

const QUICK_DESTINATIONS = [
  { label: "Tokyo", emoji: "🗾" },
  { label: "Rome", emoji: "🏛️" },
  { label: "Paris", emoji: "🗼" },
  { label: "Bali", emoji: "🌴" },
  { label: "New York", emoji: "🗽" },
  { label: "Barcelona", emoji: "🎨" },
];

const CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "INR"];

const PIPELINE_STEPS = [
  { icon: Sparkles,   text: "Travel Style agent reads your preferences" },
  { icon: MapPin,     text: "Itinerary Planner clusters attractions into walking zones" },
  { icon: Globe2,     text: "Hotel Agent finds options matching your budget tier" },
  { icon: DollarSign, text: "Budget Optimizer checks spend vs. your budget" },
  { icon: Zap,        text: "Events Agent checks what's on during your trip" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function calcNights(start: string, end: string): number | null {
  if (!start || !end) return null;
  const diff = (new Date(end).getTime() - new Date(start).getTime()) / 86400000;
  return diff > 0 ? Math.round(diff) : null;
}

function calcBudgetTier(
  budget: string,
  travelers: number,
  start: string,
  end: string,
): string | null {
  const nights = calcNights(start, end);
  const total = parseFloat(budget);
  if (!budget || isNaN(total) || !nights || nights <= 0 || travelers <= 0) return null;
  const perPersonPerDay = total / travelers / nights;
  if (perPersonPerDay < 50) return "Budget Explorer";
  if (perPersonPerDay <= 150) return "Balanced Traveler";
  return "Luxury Seeker";
}

function tierColor(tier: string | null) {
  if (tier === "Budget Explorer")
    return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
  if (tier === "Balanced Traveler") return "text-gold-400 border-gold-500/30 bg-gold-500/10";
  if (tier === "Luxury Seeker") return "text-coral-400 border-coral-500/30 bg-coral-500/10";
  return "";
}

// ── Step animation variants ───────────────────────────────────────────────────

const stepVariants = (direction: number) => ({
  initial: { opacity: 0, x: direction * 50 },
  animate: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
  },
  exit: {
    opacity: 0,
    x: -direction * 50,
    transition: { duration: 0.25, ease: [0.22, 1, 0.36, 1] as const },
  },
});

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ step, total }: { step: number; total: number }) {
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
                animate={{
                  scale: current ? 1.15 : 1,
                  backgroundColor: done
                    ? "#3b82f6"
                    : current
                      ? "rgba(59,130,246,0.15)"
                      : "rgba(255,255,255,0.06)",
                  borderColor:
                    done || current ? "#3b82f6" : "rgba(255,255,255,0.1)",
                }}
                transition={{ duration: 0.3 }}
                className="w-8 h-8 rounded-full border-2 flex items-center justify-center"
              >
                {done ? (
                  <CheckCircle2 className="w-4 h-4 text-white" />
                ) : (
                  <span
                    className={`text-xs font-bold ${
                      current ? "text-electric-400" : "text-slate-600"
                    }`}
                  >
                    {i + 1}
                  </span>
                )}
              </motion.div>
              <span
                className={`text-xs font-medium hidden sm:block text-center max-w-[72px] leading-tight ${
                  current
                    ? "text-electric-400"
                    : done
                      ? "text-slate-400"
                      : "text-slate-600"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Connecting track */}
      <div className="relative h-px bg-white/6 rounded-full mx-4 mt-1 hidden sm:block">
        <motion.div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{
            background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
          }}
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
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <div className="inline-flex w-14 h-14 rounded-2xl bg-electric-gradient items-center justify-center shadow-electric mb-5 animate-float-slow">
          <Globe2 className="w-7 h-7 text-white" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="text-slate-500 text-sm font-semibold uppercase tracking-widest mb-2"
      >
        Step 1 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="text-5xl font-bold gradient-text mb-10"
      >
        Where to?
      </motion.h1>

      {/* Big destination input */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="relative mb-8"
      >
        <MapPin className="absolute left-0 top-1/2 -translate-y-1/2 w-6 h-6 text-electric-400 pointer-events-none" />
        <input
          type="text"
          autoFocus
          placeholder="Paris, Tokyo, Bali..."
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && destination.trim()) onNext();
          }}
          className="w-full pl-10 pr-4 py-4 text-4xl font-light bg-transparent border-b-2 border-white/10 focus:border-electric-500 focus:outline-none text-slate-100 placeholder-slate-700 transition-colors duration-300"
          style={{ caretColor: "#3b82f6" }}
        />
      </motion.div>

      {/* Quick-pick pills */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="mb-10"
      >
        <p className="text-xs text-slate-600 uppercase tracking-widest font-semibold mb-4">
          Popular destinations
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {QUICK_DESTINATIONS.map(({ label, emoji }, i) => (
            <motion.button
              key={label}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.35 + i * 0.05 }}
              whileHover={{ scale: 1.06, y: -2 }}
              whileTap={{ scale: 0.96 }}
              onClick={() => setDestination(label)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium transition-all duration-200 ${
                destination === label
                  ? "border-electric-500/60 bg-electric-500/15 text-electric-400 shadow-electric-sm"
                  : "border-white/8 bg-white/4 text-slate-400 hover:border-white/20 hover:text-slate-200 hover:bg-white/8"
              }`}
            >
              <span>{emoji}</span>
              {label}
            </motion.button>
          ))}
        </div>
      </motion.div>

      {/* Next button */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
        <motion.button
          whileHover={destination.trim() ? { scale: 1.04, y: -2 } : {}}
          whileTap={destination.trim() ? { scale: 0.97 } : {}}
          onClick={onNext}
          disabled={!destination.trim()}
          className="btn-primary flex items-center gap-2 mx-auto disabled:opacity-30 disabled:cursor-not-allowed disabled:transform-none"
        >
          Continue
          <ArrowRight className="w-4 h-4" />
        </motion.button>
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
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="inline-flex w-14 h-14 rounded-2xl bg-electric-gradient items-center justify-center shadow-electric mb-5">
          <Calendar className="w-7 h-7 text-white" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="text-slate-500 text-sm font-semibold uppercase tracking-widest mb-2"
      >
        Step 2 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="text-4xl font-bold gradient-text mb-10"
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
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">
            Departure
          </label>
          <input
            type="date"
            value={startDate}
            min={today}
            onChange={(e) => {
              setStartDate(e.target.value);
              if (endDate && e.target.value >= endDate) setEndDate("");
            }}
            className="input-dark text-slate-100 [color-scheme:dark] cursor-pointer"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">
            Return
          </label>
          <input
            type="date"
            value={endDate}
            min={startDate || today}
            onChange={(e) => setEndDate(e.target.value)}
            className="input-dark text-slate-100 [color-scheme:dark] cursor-pointer"
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
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-electric-500/15 border border-electric-500/30 text-electric-400 text-sm font-semibold mb-6"
          >
            <Calendar className="w-4 h-4" />
            {nights} night{nights !== 1 ? "s" : ""}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Travel tip */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.25 }}
        className="glass-light rounded-xl p-4 mb-8 flex items-start gap-3 text-left"
      >
        <Zap className="w-4 h-4 text-gold-400 shrink-0 mt-0.5" />
        <p className="text-sm text-slate-400 leading-relaxed">
          <span className="text-gold-400 font-semibold">Planning ahead?</span>{" "}
          We&rsquo;ll automatically fetch weather forecasts for your travel window and adapt your
          itinerary for any adverse conditions.
        </p>
      </motion.div>

      {/* Navigation */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="flex items-center justify-between"
      >
        <motion.button
          whileHover={{ scale: 1.03, x: -2 }}
          whileTap={{ scale: 0.97 }}
          onClick={onBack}
          className="btn-ghost flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </motion.button>
        <motion.button
          whileHover={canNext ? { scale: 1.04, y: -2 } : {}}
          whileTap={canNext ? { scale: 0.97 } : {}}
          onClick={onNext}
          disabled={!canNext}
          className="btn-primary flex items-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed disabled:transform-none"
        >
          Continue
          <ArrowRight className="w-4 h-4" />
        </motion.button>
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
  currency,
  setCurrency,
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
  startDate: string;
  endDate: string;
  onNext: () => void;
  onBack: () => void;
}) {
  const tier = calcBudgetTier(budget, travelers, startDate, endDate);

  return (
    <div className="text-center">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="inline-flex w-14 h-14 rounded-2xl bg-electric-gradient items-center justify-center shadow-electric mb-5">
          <Users className="w-7 h-7 text-white" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="text-slate-500 text-sm font-semibold uppercase tracking-widest mb-2"
      >
        Step 3 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="text-4xl font-bold gradient-text mb-10"
      >
        Who&rsquo;s coming?
      </motion.h1>

      {/* Traveler count */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="glass-light rounded-2xl p-6 mb-5 text-left"
      >
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-5">
          Number of travelers
        </p>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-5">
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => setTravelers(Math.max(1, travelers - 1))}
              disabled={travelers <= 1}
              className="w-11 h-11 rounded-full glass border border-white/10 text-slate-200 text-xl font-light flex items-center justify-center hover:border-electric-500/40 hover:text-electric-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              −
            </motion.button>

            <div className="text-center min-w-[4rem]">
              <motion.p
                key={travelers}
                initial={{ scale: 0.7, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="text-5xl font-bold text-slate-100"
              >
                {travelers}
              </motion.p>
              <p className="text-xs text-slate-500 mt-1">
                {travelers === 1 ? "solo traveler" : "travelers"}
              </p>
            </div>

            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => setTravelers(Math.min(12, travelers + 1))}
              disabled={travelers >= 12}
              className="w-11 h-11 rounded-full glass border border-white/10 text-slate-200 text-xl font-light flex items-center justify-center hover:border-electric-500/40 hover:text-electric-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              +
            </motion.button>
          </div>

          {/* Pax visual dots */}
          <div className="hidden sm:flex flex-wrap gap-1.5 max-w-[120px] justify-end">
            {Array.from({ length: Math.min(travelers, 12) }).map((_, i) => (
              <motion.div
                key={i}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: i * 0.04 }}
                className="w-4 h-4 rounded-full bg-electric-500/60"
              />
            ))}
          </div>
        </div>
      </motion.div>

      {/* Budget */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-light rounded-2xl p-6 mb-8 text-left"
      >
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-5">
          Total trip budget{" "}
          <span className="normal-case text-slate-700 font-normal">(optional)</span>
        </p>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <DollarSign className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
            <input
              type="number"
              min="0"
              placeholder="5000"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="input-dark pl-10 text-slate-100"
            />
          </div>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="input-dark w-28 shrink-0 bg-space-800 cursor-pointer"
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c} className="bg-space-800">
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Budget tier badge */}
        <AnimatePresence mode="wait">
          {tier && (
            <motion.div
              key={tier}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className={`inline-flex items-center gap-2 mt-4 px-3 py-1.5 rounded-full border text-xs font-semibold ${tierColor(tier)}`}
            >
              <Sparkles className="w-3 h-3" />
              {tier}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Navigation */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="flex items-center justify-between"
      >
        <motion.button
          whileHover={{ scale: 1.03, x: -2 }}
          whileTap={{ scale: 0.97 }}
          onClick={onBack}
          className="btn-ghost flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.04, y: -2 }}
          whileTap={{ scale: 0.97 }}
          onClick={onNext}
          className="btn-primary flex items-center gap-2"
        >
          Continue
          <ArrowRight className="w-4 h-4" />
        </motion.button>
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
  onBack: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  error: string | null;
}) {
  const nights = calcNights(startDate, endDate);
  const tier = calcBudgetTier(budget, travelers, startDate, endDate);

  const formatDate = (d: string) =>
    d
      ? new Date(d).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
      : "—";

  return (
    <div className="text-center">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="inline-flex w-14 h-14 rounded-2xl bg-electric-gradient items-center justify-center shadow-electric mb-5 animate-pulse-glow">
          <Sparkles className="w-7 h-7 text-white" />
        </div>
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="text-slate-500 text-sm font-semibold uppercase tracking-widest mb-2"
      >
        Step 4 of 4
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="text-4xl font-bold gradient-text mb-8"
      >
        Ready to launch?
      </motion.h1>

      {/* Summary card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="glass-light rounded-2xl p-6 mb-5 text-left"
      >
        <div className="flex items-center gap-2 mb-4">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
            Trip summary
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-slate-600 mb-1 flex items-center gap-1">
              <MapPin className="w-3 h-3" /> Destination
            </p>
            <p className="text-xl font-bold text-slate-100">{destination}</p>
          </div>

          <div>
            <p className="text-xs text-slate-600 mb-1 flex items-center gap-1">
              <Users className="w-3 h-3" /> Travelers
            </p>
            <p className="text-xl font-bold text-slate-100">
              {travelers}{" "}
              <span className="text-sm font-normal text-slate-400">
                {travelers === 1 ? "person" : "people"}
              </span>
            </p>
          </div>

          <div>
            <p className="text-xs text-slate-600 mb-1 flex items-center gap-1">
              <Calendar className="w-3 h-3" /> Dates
            </p>
            <p className="text-sm font-semibold text-slate-200">
              {formatDate(startDate)} – {formatDate(endDate)}
            </p>
            {nights !== null && (
              <p className="text-xs text-slate-500 mt-0.5">{nights} nights</p>
            )}
          </div>

          <div>
            <p className="text-xs text-slate-600 mb-1 flex items-center gap-1">
              <DollarSign className="w-3 h-3" /> Budget
            </p>
            {budget ? (
              <>
                <p className="text-sm font-semibold text-slate-200">
                  {currency} {parseFloat(budget).toLocaleString()}
                </p>
                {tier && (
                  <p
                    className={`text-xs mt-0.5 font-medium ${tierColor(tier).split(" ")[0]}`}
                  >
                    {tier}
                  </p>
                )}
              </>
            ) : (
              <p className="text-sm text-slate-500 italic">Not set</p>
            )}
          </div>
        </div>
      </motion.div>

      {/* Agent pipeline */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass-light rounded-2xl p-6 mb-6 text-left"
      >
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
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
              <div className="w-7 h-7 rounded-lg bg-electric-500/15 border border-electric-500/25 flex items-center justify-center shrink-0">
                <Icon className="w-3.5 h-3.5 text-electric-400" />
              </div>
              <p className="text-sm text-slate-400 leading-snug">
                <span className="text-electric-400 font-semibold">✦</span> {text}
              </p>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="mb-5 px-4 py-3 rounded-xl bg-coral-500/10 border border-coral-500/30 text-coral-400 text-sm text-left"
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
        <motion.button
          whileHover={{ scale: 1.03, x: -2 }}
          whileTap={{ scale: 0.97 }}
          onClick={onBack}
          disabled={isSubmitting}
          className="btn-ghost flex items-center gap-2 disabled:opacity-50"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </motion.button>

        <motion.button
          whileHover={!isSubmitting ? { scale: 1.04, y: -2 } : {}}
          whileTap={!isSubmitting ? { scale: 0.97 } : {}}
          onClick={onSubmit}
          disabled={isSubmitting}
          className="btn-primary flex items-center gap-3 text-base px-8 py-3 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Building your trip...
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5" />
              ✦ Start Planning
            </>
          )}
        </motion.button>
      </motion.div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NewTripPage() {
  const router = useRouter();
  const { token, _hasHydrated } = useAuthStore();

  const [step, setStep]           = useState(0);
  const [direction, setDirection] = useState(1);

  // Form state
  const [destination, setDestination] = useState("");
  const [startDate, setStartDate]     = useState("");
  const [endDate, setEndDate]         = useState("");
  const [travelers, setTravelers]     = useState(1);
  const [budget, setBudget]           = useState("");
  const [currency, setCurrency]       = useState("USD");

  // Submit state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError]               = useState<string | null>(null);

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
      });
      router.push(`/trips/${trip.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { detail?: string; message?: string } | string | null;
        const msg =
          typeof detail === "string"
            ? detail
            : detail?.detail ?? detail?.message ?? "Something went wrong. Please try again.";
        setError(msg);
      } else {
        setError("Something went wrong. Please try again.");
      }
      setIsSubmitting(false);
    }
  }

  const variants = stepVariants(direction);

  return (
    <div className="relative min-h-screen bg-space-900 overflow-x-hidden">
      {/* Ambient background glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] rounded-full bg-electric-500/6 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] rounded-full bg-purple-600/6 blur-[120px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-electric-600/4 blur-[160px]" />
      </div>

      <NavBar />

      <main className="relative z-10 min-h-screen flex flex-col items-center justify-center px-4 pt-20 pb-16">
        <div className="w-full max-w-xl">
          {/* Progress indicator */}
          <ProgressBar step={step} total={4} />

          {/* Step card */}
          <div className="glass-card p-8 sm:p-10 relative overflow-hidden">
            {/* Inner corner glows */}
            <div className="pointer-events-none absolute -top-20 -right-20 w-48 h-48 rounded-full bg-electric-500/8 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-20 -left-20 w-48 h-48 rounded-full bg-purple-600/6 blur-3xl" />

            <AnimatePresence mode="wait" initial={false}>
              {step === 0 && (
                <motion.div
                  key="step-0"
                  variants={variants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  <StepDestination
                    destination={destination}
                    setDestination={setDestination}
                    onNext={goNext}
                  />
                </motion.div>
              )}

              {step === 1 && (
                <motion.div
                  key="step-1"
                  variants={variants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
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
                <motion.div
                  key="step-2"
                  variants={variants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  <StepTravelersBudget
                    travelers={travelers}
                    setTravelers={setTravelers}
                    budget={budget}
                    setBudget={setBudget}
                    currency={currency}
                    setCurrency={setCurrency}
                    startDate={startDate}
                    endDate={endDate}
                    onNext={goNext}
                    onBack={goBack}
                  />
                </motion.div>
              )}

              {step === 3 && (
                <motion.div
                  key="step-3"
                  variants={variants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  <StepLaunch
                    destination={destination}
                    startDate={startDate}
                    endDate={endDate}
                    travelers={travelers}
                    budget={budget}
                    currency={currency}
                    onBack={goBack}
                    onSubmit={handleSubmit}
                    isSubmitting={isSubmitting}
                    error={error}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Footer hint */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="text-center text-xs text-slate-700 mt-6"
          >
            Powered by multi-agent AI — hotels, weather, events, and budget auto-optimized.
          </motion.p>
        </div>
      </main>
    </div>
  );
}
