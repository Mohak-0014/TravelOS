"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const PACE_OPTIONS = ["relaxed", "moderate", "packed"];
const LUXURY_OPTIONS = ["budget", "mid", "luxury"];
const BUDGET_OPTIONS = ["frugal", "balanced", "splurge"];
const INTEREST_OPTIONS = [
  "Museums", "Food", "Outdoors", "History", "Art", "Shopping",
  "Nightlife", "Architecture", "Nature", "Sports",
];

export default function OnboardingPage() {
  const router = useRouter();
  const [pace, setPace] = useState<string | null>(null);
  const [luxury, setLuxury] = useState<string | null>(null);
  const [budget, setBudget] = useState<string | null>(null);
  const [interests, setInterests] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  function toggleInterest(item: string) {
    setInterests((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item],
    );
  }

  async function handleSave() {
    setLoading(true);
    try {
      await api.put("/api/v1/preferences", {
        pace,
        luxury_tier: luxury,
        budget_behavior: budget,
        interests: interests.map((i) => i.toLowerCase()),
      });
      router.push("/trips");
    } catch {
      router.push("/trips");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow p-8 w-full max-w-lg">
        <h1 className="text-xl font-bold text-gray-900 mb-1">Set your travel style</h1>
        <p className="text-sm text-gray-500 mb-6">
          This helps your AI agents plan trips that fit you. You can change these anytime.
        </p>

        <div className="space-y-6">
          <Section label="Travel pace">
            <Chips options={PACE_OPTIONS} selected={pace} onSelect={setPace} />
          </Section>

          <Section label="Accommodation tier">
            <Chips options={LUXURY_OPTIONS} selected={luxury} onSelect={setLuxury} />
          </Section>

          <Section label="Budget style">
            <Chips options={BUDGET_OPTIONS} selected={budget} onSelect={setBudget} />
          </Section>

          <Section label="Interests">
            <div className="flex flex-wrap gap-2">
              {INTEREST_OPTIONS.map((item) => (
                <button
                  key={item}
                  onClick={() => toggleInterest(item)}
                  className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                    interests.includes(item)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          </Section>
        </div>

        <div className="flex gap-3 mt-8">
          <button
            onClick={() => router.push("/trips")}
            className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-50 transition-colors"
          >
            Skip for now
          </button>
          <button
            onClick={handleSave}
            disabled={loading}
            className="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Saving…" : "Save preferences"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-sm font-medium text-gray-700 mb-2">{label}</p>
      {children}
    </div>
  );
}

function Chips({
  options,
  selected,
  onSelect,
}: {
  options: string[];
  selected: string | null;
  onSelect: (v: string) => void;
}) {
  return (
    <div className="flex gap-2 flex-wrap">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onSelect(opt)}
          className={`px-3 py-1.5 rounded-full text-sm border capitalize transition-colors ${
            selected === opt
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
