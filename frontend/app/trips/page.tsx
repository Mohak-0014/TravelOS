"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TripOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import Link from "next/link";

function TripCard({ trip }: { trip: TripOut }) {
  const nights =
    Math.ceil(
      (new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) /
        (1000 * 60 * 60 * 24),
    ) + 1;

  const statusColors: Record<string, string> = {
    planning: "bg-yellow-100 text-yellow-800",
    active: "bg-green-100 text-green-800",
    completed: "bg-gray-100 text-gray-600",
    cancelled: "bg-red-100 text-red-700",
  };

  return (
    <Link href={`/trips/${trip.id}`}>
      <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer">
        <div className="flex items-start justify-between mb-2">
          <h2 className="font-semibold text-gray-900 text-base leading-snug">{trip.title}</h2>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ml-2 shrink-0 ${
              statusColors[trip.status] ?? "bg-gray-100 text-gray-600"
            }`}
          >
            {trip.status}
          </span>
        </div>
        <p className="text-sm text-gray-600 mb-3">
          {trip.destination_city}
          {trip.destination_country ? `, ${trip.destination_country}` : ""}
        </p>
        <div className="flex gap-4 text-xs text-gray-500">
          <span>
            {new Date(trip.start_date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}{" "}
            –{" "}
            {new Date(trip.end_date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
          <span>{nights} nights</span>
          {trip.num_travelers > 1 && <span>{trip.num_travelers} travelers</span>}
          {trip.budget_total && (
            <span>
              {trip.budget_currency} {trip.budget_total.toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export default function TripsPage() {
  const router = useRouter();
  const { token, user } = useAuthStore();

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  const { data: trips, isLoading, error } = useQuery<TripOut[]>({
    queryKey: ["trips"],
    queryFn: () => api.get<TripOut[]>("/api/v1/trips"),
    enabled: !!token,
  });

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-bold text-gray-900">TravelOS</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{user?.email}</span>
          <Link
            href="/onboarding"
            className="text-sm text-blue-600 hover:underline"
          >
            Preferences
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">My Trips</h2>
          <Link
            href="/trips/new"
            className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            + New Trip
          </Link>
        </div>

        {isLoading && (
          <div className="text-center text-gray-500 py-16 text-sm">Loading trips…</div>
        )}

        {error && (
          <div className="text-center text-red-600 py-16 text-sm">
            Could not load trips. Is the backend running?
          </div>
        )}

        {trips && trips.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 text-sm mb-4">No trips yet.</p>
            <Link
              href="/trips/new"
              className="bg-blue-600 text-white text-sm font-medium px-5 py-2.5 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Plan your first trip
            </Link>
          </div>
        )}

        {trips && trips.length > 0 && (
          <div className="flex flex-col gap-3">
            {trips.map((t) => (
              <TripCard key={t.id} trip={t} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
