"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { TripOut, ItineraryItemOut, ApprovalOut, ChatResponse, ChatSource, WeatherDay, HotelCandidateOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

const TripMap = dynamic(() => import("./TripMap"), {
  ssr: false,
  loading: () => <div className="h-[300px] bg-gray-100 rounded-xl animate-pulse" />,
});

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
};

const STATUS_COLORS: Record<string, string> = {
  planning: "bg-yellow-100 text-yellow-800",
  generating: "bg-blue-100 text-blue-800",
  awaiting_approval: "bg-orange-100 text-orange-900",
  planned: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

const ITEM_ICONS: Record<string, string> = {
  activity: "🎭",
  meal: "🍽",
  transport: "🚌",
  lodging: "🏨",
  free: "☀️",
};

export default function TripDetailPage() {
  const { tripId } = useParams<{ tripId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, _hasHydrated } = useAuthStore();

  useEffect(() => {
    if (_hasHydrated && !token) router.replace("/login");
  }, [_hasHydrated, token, router]);

  // ── Queries ──────────────────────────────────────────────────────────────────

  const { data: trip, isLoading: tripLoading } = useQuery<TripOut>({
    queryKey: ["trip", tripId],
    queryFn: () => api.get<TripOut>(`/api/v1/trips/${tripId}`),
    refetchInterval: (q) => (q.state.data?.status === "generating" ? 3000 : false),
    enabled: !!token && !!tripId,
  });

  const { data: weatherDays = [] } = useQuery<WeatherDay[]>({
    queryKey: ["weather", tripId],
    queryFn: () => api.get<WeatherDay[]>(`/api/v1/trips/${tripId}/weather`),
    enabled: !!token && !!tripId,
    staleTime: 30 * 60 * 1000,
  });

  const { data: items = [] } = useQuery<ItineraryItemOut[]>({
    queryKey: ["itinerary", tripId],
    queryFn: () => api.get<ItineraryItemOut[]>(`/api/v1/trips/${tripId}/itinerary`),
    enabled: !!trip && trip.status !== "planning",
    staleTime: 10_000,
  });

  const { data: hotels = [] } = useQuery<HotelCandidateOut[]>({
    queryKey: ["hotels", tripId],
    queryFn: () => api.get<HotelCandidateOut[]>(`/api/v1/trips/${tripId}/hotels`),
    enabled: !!token && !!tripId && !!trip && trip.status !== "planning",
    staleTime: 60_000,
  });

  const { data: pendingApprovals = [] } = useQuery<ApprovalOut[]>({
    queryKey: ["approvals", tripId, "pending"],
    queryFn: () =>
      api.get<ApprovalOut[]>(`/api/v1/trips/${tripId}/approvals`, { status: "pending" }),
    enabled: trip?.status === "awaiting_approval",
  });

  // Invalidate related caches when status transitions to planned or awaiting_approval
  const prevStatusRef = useRef<string | undefined>();
  useEffect(() => {
    const prev = prevStatusRef.current;
    const curr = trip?.status;
    prevStatusRef.current = curr;
    if (!prev || prev === curr) return;
    if (curr === "planned" || curr === "awaiting_approval") {
      queryClient.invalidateQueries({ queryKey: ["itinerary", tripId] });
    }
    if (curr === "awaiting_approval") {
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
    }
  }, [trip?.status, queryClient, tripId]);

  // ── Generate ─────────────────────────────────────────────────────────────────

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    try {
      await api.post(`/api/v1/trips/${tripId}/itinerary/generate`);
      queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { message?: string } | null;
        setGenerateError(detail?.message ?? `Error ${err.status}`);
      } else {
        setGenerateError("Could not start generation. Is the backend running?");
      }
    } finally {
      setGenerating(false);
    }
  }

  // ── Approvals ─────────────────────────────────────────────────────────────────

  async function handleDecision(approvalId: string, decision: "approved" | "rejected") {
    try {
      await api.post(`/api/v1/approvals/${approvalId}`, { decision });
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
      queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
      queryClient.invalidateQueries({ queryKey: ["itinerary", tripId] });
    } catch {
      // silently ignore — stale UI will auto-refresh on next poll
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────────

  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function handleChatSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", text: q }]);
    setChatLoading(true);
    try {
      const res = await api.post<ChatResponse>(`/api/v1/trips/${tripId}/chat`, { question: q });
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", text: res.answer, sources: res.sources },
      ]);
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Sorry, I couldn't answer that right now. Please try again." },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  // ── Early returns ─────────────────────────────────────────────────────────────

  if (!_hasHydrated) return null;

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

  // ── Derived values ────────────────────────────────────────────────────────────

  const nights = Math.ceil(
    (new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) /
      (1000 * 60 * 60 * 24),
  );

  const itemsByDay = items.reduce<Record<number, ItineraryItemOut[]>>((acc, item) => {
    (acc[item.day_number] ??= []).push(item);
    return acc;
  }, {});

  const pinnedItems = items.filter((i) => i.latitude != null && i.longitude != null);

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <Link href="/trips" className="text-sm text-blue-600 hover:underline">
          ← My trips
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        {/* Trip header */}
        <div>
          <div className="flex items-start gap-3 mb-1">
            <h1 className="text-2xl font-bold text-gray-900 flex-1">{trip.title}</h1>
            <span
              className={`text-xs px-2.5 py-1 rounded-full font-medium capitalize shrink-0 mt-1 ${
                STATUS_COLORS[trip.status] ?? "bg-gray-100 text-gray-500"
              }`}
            >
              {trip.status.replace(/_/g, " ")}
            </span>
          </div>
          <p className="text-sm text-gray-500">
            {trip.destination_city}
            {trip.destination_country ? `, ${trip.destination_country}` : ""} ·{" "}
            {new Date(trip.start_date + "T00:00:00").toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}{" "}
            –{" "}
            {new Date(trip.end_date + "T00:00:00").toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}{" "}
            · {nights} night{nights !== 1 ? "s" : ""} · {trip.num_travelers} traveler
            {trip.num_travelers !== 1 ? "s" : ""}
            {trip.budget_total
              ? ` · ${trip.budget_currency} ${trip.budget_total.toLocaleString()}`
              : ""}
          </p>
        </div>

        {/* Generate / status banners */}
        {trip.status === "planning" && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <p className="text-sm text-gray-700 mb-3">
              No itinerary yet. Let the AI agents plan it for you.
            </p>
            {generateError && (
              <p className="text-sm text-red-600 mb-3">{generateError}</p>
            )}
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {generating ? "Queuing…" : "✨ Generate AI itinerary"}
            </button>
          </div>
        )}

        {trip.status === "generating" && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 flex items-center gap-3">
            <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin shrink-0" />
            <div>
              <p className="text-sm font-medium text-blue-800">Generating your itinerary…</p>
              <p className="text-xs text-blue-600 mt-0.5">
                This takes 30–60 s. Checking for updates automatically.
              </p>
            </div>
          </div>
        )}

        {trip.status === "failed" && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5">
            <p className="text-sm font-medium text-red-700 mb-2">Generation failed.</p>
            {generateError && <p className="text-xs text-red-600 mb-2">{generateError}</p>}
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="text-sm text-red-700 underline hover:no-underline disabled:opacity-50"
            >
              {generating ? "Queuing…" : "Try again"}
            </button>
          </div>
        )}

        {/* Pending approvals */}
        {trip.status === "awaiting_approval" && pendingApprovals.length > 0 && (
          <div className="bg-orange-50 border border-orange-200 rounded-xl p-5 space-y-3">
            <h2 className="text-sm font-semibold text-orange-900">
              Pending approvals ({pendingApprovals.length})
            </h2>
            {pendingApprovals.map((a) => (
              <div key={a.id} className="bg-white rounded-lg border border-orange-200 p-4">
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                  {a.change_type.replace(/_/g, " ")}
                </p>
                <p className="text-sm text-gray-800 mb-3">{a.summary}</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleDecision(a.id, "approved")}
                    className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 transition-colors"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleDecision(a.id, "rejected")}
                    className="text-xs bg-white border border-gray-300 text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Itinerary — hidden until generation has been attempted */}
        {trip.status !== "planning" && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-900">Itinerary</h2>
            {trip.status === "planned" && (
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="text-xs text-blue-600 hover:underline disabled:opacity-50"
              >
                Regenerate
              </button>
            )}
          </div>

          {Object.keys(itemsByDay).length === 0 ? (
            <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 text-center">
              <p className="text-gray-500 text-sm">
                {trip.status === "generating"
                  ? "Building your itinerary…"
                  : "No items yet. Items will appear here once agents finish."}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {Object.entries(itemsByDay)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([day, dayItems]) => (
                  <div key={day} className="bg-white rounded-xl border border-gray-200 p-4">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
                      Day {day}
                      {dayItems[0]?.item_date
                        ? ` · ${new Date(dayItems[0].item_date + "T00:00:00").toLocaleDateString(
                            "en-US",
                            { weekday: "short", month: "short", day: "numeric" },
                          )}`
                        : ""}
                    </p>
                    <div className="flex flex-col gap-3">
                      {[...dayItems]
                        .sort((a, b) => a.sort_order - b.sort_order)
                        .map((item) => (
                          <div key={item.id} className="flex items-start gap-3 text-sm">
                            <span className="text-gray-400 text-xs w-14 shrink-0 pt-0.5 tabular-nums">
                              {item.start_time ?? "—"}
                            </span>
                            <span className="text-base w-5 shrink-0" title={item.item_type}>
                              {ITEM_ICONS[item.item_type] ?? "📍"}
                            </span>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-gray-900 leading-snug">{item.title}</p>
                              {item.address && (
                                <p className="text-xs text-gray-400 truncate mt-0.5">
                                  {item.address}
                                </p>
                              )}
                              {item.description && (
                                <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                                  {item.description}
                                </p>
                              )}
                            </div>
                            {item.est_cost != null && (
                              <span className="text-xs text-gray-500 shrink-0 tabular-nums">
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
        </div>
        )}

        {/* Hotels */}
        {hotels.length > 0 && (
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-3">Hotel Options</h2>
            <div className="flex flex-col gap-3">
              {hotels.map((hotel) => (
                <div
                  key={hotel.id}
                  className={`bg-white rounded-xl border p-4 flex gap-4 ${
                    hotel.is_selected ? "border-blue-400 ring-1 ring-blue-300" : "border-gray-200"
                  }`}
                >
                  {hotel.image_url && (
                    <img
                      src={hotel.image_url}
                      alt={hotel.name}
                      className="w-20 h-20 rounded-lg object-cover shrink-0"
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium text-gray-900 leading-snug truncate">{hotel.name}</p>
                        {hotel.star_rating != null && (
                          <p className="text-xs text-amber-500 mt-0.5">
                            {"★".repeat(Math.round(hotel.star_rating))}
                            {"☆".repeat(Math.max(0, 5 - Math.round(hotel.star_rating)))}
                            <span className="text-gray-400 ml-1">{hotel.star_rating.toFixed(1)}</span>
                          </p>
                        )}
                        {hotel.address && (
                          <p className="text-xs text-gray-400 truncate mt-0.5">{hotel.address}</p>
                        )}
                        <div className="flex flex-wrap gap-2 mt-1.5">
                          {hotel.meal_plan && (
                            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                              {hotel.meal_plan}
                            </span>
                          )}
                          {hotel.refundable != null && (
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full ${
                                hotel.refundable
                                  ? "bg-green-100 text-green-700"
                                  : "bg-red-50 text-red-600"
                              }`}
                            >
                              {hotel.refundable ? "Refundable" : "Non-refundable"}
                            </span>
                          )}
                          {hotel.is_selected && (
                            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
                              Selected
                            </span>
                          )}
                        </div>
                      </div>
                      {(hotel.price_per_night != null || hotel.price_total != null) && (
                        <div className="text-right shrink-0">
                          {hotel.price_per_night != null && (
                            <p className="text-sm font-semibold text-gray-900 tabular-nums">
                              {hotel.price_currency ?? ""} {hotel.price_per_night.toLocaleString()}
                              <span className="text-xs font-normal text-gray-400">/night</span>
                            </p>
                          )}
                          {hotel.price_total != null && (
                            <p className="text-xs text-gray-500 tabular-nums">
                              {hotel.price_currency ?? ""} {hotel.price_total.toLocaleString()} total
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Weather */}
        {weatherDays.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <h2 className="text-base font-semibold text-gray-900">Weather</h2>
              {weatherDays.some((d) => d.is_climate_normal) && (
                <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full">
                  Historical averages shown for dates beyond 14 days
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {weatherDays.map((day) => (
                <div
                  key={day.date}
                  className={`rounded-xl border p-3 text-sm ${
                    day.is_adverse
                      ? "bg-red-50 border-red-200"
                      : day.is_climate_normal
                        ? "bg-amber-50 border-amber-200"
                        : "bg-white border-gray-200"
                  }`}
                >
                  <p className="text-xs text-gray-400 mb-1">
                    {new Date(day.date + "T00:00:00").toLocaleDateString("en-US", {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                  <p className="font-medium text-gray-800 leading-tight text-xs">
                    {day.condition_label}
                    {day.is_adverse && " ⚠️"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {Math.round(day.temp_min_c)}–{Math.round(day.temp_max_c)}°C
                  </p>
                  {day.precipitation_mm > 0 && (
                    <p className="text-xs text-blue-500 mt-0.5">
                      💧 {day.precipitation_mm} mm
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Map */}
        {trip.latitude != null && trip.longitude != null && pinnedItems.length > 0 && (
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-3">Map</h2>
            <TripMap
              items={pinnedItems}
              centerLat={trip.latitude}
              centerLng={trip.longitude}
            />
          </div>
        )}

        {/* Concierge chat */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <button
            onClick={() => setChatOpen((v) => !v)}
            className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition-colors"
          >
            <div>
              <p className="text-sm font-semibold text-gray-900">Ask the Concierge</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Restaurants, attractions, packing advice — anything about your trip
              </p>
            </div>
            <span className="text-gray-400 text-xs ml-4">{chatOpen ? "▲" : "▼"}</span>
          </button>

          {chatOpen && (
            <div className="border-t border-gray-100">
              {/* Message history */}
              <div className="px-5 py-3 max-h-72 overflow-y-auto space-y-3">
                {chatMessages.length === 0 && (
                  <p className="text-xs text-gray-400 text-center py-4">
                    Try: &quot;Best restaurant near the Eiffel Tower&quot; or &quot;What should I
                    pack?&quot;
                  </p>
                )}
                {chatMessages.map((msg, i) => (
                  <div key={i}>
                    <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-xs text-sm px-3.5 py-2 rounded-2xl leading-relaxed ${
                          msg.role === "user"
                            ? "bg-blue-600 text-white rounded-br-sm"
                            : "bg-gray-100 text-gray-800 rounded-bl-sm"
                        }`}
                      >
                        {msg.text}
                      </div>
                    </div>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5 ml-1">
                        {msg.sources.slice(0, 6).map((s, j) => (
                          <span
                            key={j}
                            className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full border border-gray-200"
                          >
                            {s.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {chatLoading && (
                  <div className="flex gap-1 items-center px-3 py-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <form
                onSubmit={handleChatSubmit}
                className="flex gap-2 px-4 pb-4 pt-2 border-t border-gray-100"
              >
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={chatLoading}
                  placeholder="Ask anything about your trip…"
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatInput.trim()}
                  className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-40 transition-colors"
                >
                  Send
                </button>
              </form>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
