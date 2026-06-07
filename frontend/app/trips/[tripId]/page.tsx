"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TripOut, ItineraryItemOut } from "@/lib/api";
import Link from "next/link";

export default function TripDetailPage() {
  const { tripId } = useParams<{ tripId: string }>();

  const { data: trip, isLoading: tripLoading } = useQuery<TripOut>({
    queryKey: ["trip", tripId],
    queryFn: () => api.get<TripOut>(`/api/v1/trips/${tripId}`),
  });

  const { data: items } = useQuery<ItineraryItemOut[]>({
    queryKey: ["itinerary", tripId],
    queryFn: () => api.get<ItineraryItemOut[]>(`/api/v1/trips/${tripId}/itinerary`),
    enabled: !!trip,
  });

  if (tripLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500 text-sm">Loading…</p>
      </div>
    );
  }

  if (!trip) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500 text-sm">Trip not found.</p>
      </div>
    );
  }

  const nights = Math.ceil(
    (new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) /
      (1000 * 60 * 60 * 24),
  );

  const itemsByDay = (items ?? []).reduce<Record<number, ItineraryItemOut[]>>((acc, item) => {
    (acc[item.day_number] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <Link href="/trips" className="text-sm text-blue-600 hover:underline">
          ← My trips
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {/* Trip header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">{trip.title}</h1>
          <p className="text-gray-500 text-sm mt-1">
            {trip.destination_city}
            {trip.destination_country ? `, ${trip.destination_country}` : ""} ·{" "}
            {new Date(trip.start_date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}{" "}
            –{" "}
            {new Date(trip.end_date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}{" "}
            · {nights} nights · {trip.num_travelers} traveler
            {trip.num_travelers > 1 ? "s" : ""}
          </p>
          {trip.latitude && trip.longitude && (
            <p className="text-xs text-gray-400 mt-0.5">
              {trip.latitude.toFixed(4)}, {trip.longitude.toFixed(4)}
            </p>
          )}
        </div>

        {/* Itinerary */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Itinerary</h2>
          <span className="text-xs text-gray-400">
            AI generation available in Phase 2
          </span>
        </div>

        {Object.keys(itemsByDay).length === 0 ? (
          <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 text-center">
            <p className="text-gray-500 text-sm">No itinerary items yet.</p>
            <p className="text-gray-400 text-xs mt-1">
              Items added by agents will appear here day by day.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {Object.entries(itemsByDay)
              .sort(([a], [b]) => Number(a) - Number(b))
              .map(([day, dayItems]) => (
                <div key={day} className="bg-white rounded-xl border border-gray-200 p-4">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    Day {day}
                  </p>
                  <div className="flex flex-col gap-2">
                    {dayItems
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((item) => (
                        <div
                          key={item.id}
                          className="flex items-start gap-3 text-sm text-gray-700"
                        >
                          <span className="text-gray-400 text-xs w-16 shrink-0 pt-0.5">
                            {item.start_time ?? "—"}
                          </span>
                          <div>
                            <p className="font-medium">{item.title}</p>
                            {item.source_provider && (
                              <p className="text-xs text-gray-400">
                                via {item.source_provider}
                              </p>
                            )}
                          </div>
                          {item.est_cost && (
                            <span className="ml-auto text-xs text-gray-500 shrink-0">
                              {item.est_cost_currency ?? ""} {item.est_cost}
                            </span>
                          )}
                        </div>
                      ))}
                  </div>
                </div>
              ))}
          </div>
        )}
      </main>
    </div>
  );
}
