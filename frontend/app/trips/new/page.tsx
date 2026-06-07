"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { TripOut } from "@/lib/api";
import Link from "next/link";

export default function NewTripPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [travelers, setTravelers] = useState(1);
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (endDate < startDate) {
      setError("End date must be on or after the start date.");
      return;
    }

    setLoading(true);
    try {
      const trip = await api.post<TripOut>("/api/v1/trips", {
        title,
        destination_city: city,
        destination_country: country || null,
        start_date: startDate,
        end_date: endDate,
        num_travelers: travelers,
        budget_total: budget ? parseFloat(budget) : null,
        budget_currency: currency,
      });
      await queryClient.invalidateQueries({ queryKey: ["trips"] });
      router.push(`/trips/${trip.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { message?: string } | null;
        setError(detail?.message ?? `Error ${err.status}`);
      } else {
        setError("Could not create trip. Is the backend running?");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <Link href="/trips" className="text-sm text-blue-600 hover:underline">
          ← Back to trips
        </Link>
      </header>

      <main className="max-w-lg mx-auto px-4 py-8">
        <h1 className="text-xl font-bold text-gray-900 mb-6">Plan a new trip</h1>

        <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 p-6 flex flex-col gap-5">
          <Field label="Trip title" required>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Summer in Japan"
              className={inputCls}
            />
          </Field>

          <div className="flex gap-3">
            <Field label="City" required className="flex-1">
              <input
                type="text"
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Tokyo"
                className={inputCls}
              />
            </Field>
            <Field label="Country code" className="w-24">
              <input
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value.toUpperCase())}
                placeholder="JP"
                maxLength={2}
                className={inputCls}
              />
            </Field>
          </div>

          <div className="flex gap-3">
            <Field label="Start date" required className="flex-1">
              <input
                type="date"
                required
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="End date" required className="flex-1">
              <input
                type="date"
                required
                value={endDate}
                min={startDate}
                onChange={(e) => setEndDate(e.target.value)}
                className={inputCls}
              />
            </Field>
          </div>

          <Field label="Travelers">
            <input
              type="number"
              min={1}
              max={20}
              value={travelers}
              onChange={(e) => setTravelers(parseInt(e.target.value) || 1)}
              className={inputCls}
            />
          </Field>

          <div className="flex gap-3">
            <Field label="Budget (optional)" className="flex-1">
              <input
                type="number"
                min={0}
                step={100}
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="3000"
                className={inputCls}
              />
            </Field>
            <Field label="Currency" className="w-24">
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className={inputCls}
              >
                {["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "INR"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Creating trip…" : "Create trip"}
          </button>
        </form>
      </main>
    </div>
  );
}

const inputCls =
  "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

function Field({
  label,
  required,
  className,
  children,
}: {
  label: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={className}>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}
