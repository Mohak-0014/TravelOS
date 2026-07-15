"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { ChevronRight, AlertCircle, Loader2, Sparkles, Compass, MapPin, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  TripOut,
  ItineraryItemOut,
  ApprovalOut,
  ChatResponse,
  WeatherDay,
  HotelCandidateOut,
  TripUpdate,
  TripEventOut,
  FlightOfferOut,
} from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { flightOriginKey, genStartKey } from "@/lib/constants";
import { convertToBudgetCurrency } from "@/lib/currency";
import { EASE } from "@/lib/motion";
import NavBar from "@/components/ui/NavBar";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Tabs } from "@/components/ui/Tabs";
import { AgentProgress } from "@/components/trip/AgentProgress";
import { ApprovalCard } from "@/components/trip/ApprovalCards";
import { TripHero } from "@/components/trip/TripHero";
import { BudgetPanel } from "@/components/trip/BudgetPanel";
import { ItinerarySection, EmptyItineraryState } from "@/components/trip/ItineraryDay";
import { HotelsPanel } from "@/components/trip/HotelsPanel";
import { FlightsPanel } from "@/components/trip/FlightsPanel";
import { EventsPanel } from "@/components/trip/EventsPanel";
import { PackingList } from "@/components/trip/PackingList";
import { SectionNav } from "@/components/trip/SectionNav";
import { ConciergeThread, type ChatMessage } from "@/components/trip/ConciergeThread";
import { MapCard } from "@/components/trip/MapCard";
import { EditTripModal } from "@/components/trip/EditTripModal";

// ── Budget category palette (mirrors the map-pin legend for cross-widget consistency) ──
const BUDGET_COLORS: Record<string, string> = {
  Flights: "#6BB6FF",
  Lodging: "#FF9E64",
  Activities: "#D9A05B",
  Meals: "#FFC46B",
  Transport: "#3ECF8E",
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
    refetchInterval: (q) => (q.state.data?.status === "generating" ? 2000 : false),
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

  const { data: tripEvents = [] } = useQuery<TripEventOut[]>({
    queryKey: ["events", tripId],
    queryFn: () => api.getTripEvents(tripId as string),
    enabled: !!token && !!tripId && !!trip && trip.status !== "planning",
    staleTime: 120_000,
  });

  const [flightOrigin, setFlightOrigin] = useState("");
  const [flightSearch, setFlightSearch] = useState("");
  const [selectedFlight, setSelectedFlight] = useState<FlightOfferOut | null>(null);

  // Auto-fill flight origin saved during trip creation
  useEffect(() => {
    if (!tripId) return;
    const saved = sessionStorage.getItem(flightOriginKey(tripId as string));
    if (saved && saved.length === 3) {
      setFlightOrigin(saved);
      setFlightSearch(saved);
    }
  }, [tripId]);

  const { data: flights = [], isFetching: flightsFetching } = useQuery<FlightOfferOut[]>({
    queryKey: ["flights", tripId, flightSearch],
    queryFn: () => api.getTripFlights(tripId as string, flightSearch),
    enabled: !!token && !!tripId && flightSearch.length === 3,
    staleTime: 3600_000,
  });

  const { data: pendingApprovals = [] } = useQuery<ApprovalOut[]>({
    queryKey: ["approvals", tripId, "pending"],
    queryFn: () => api.get<ApprovalOut[]>(`/api/v1/trips/${tripId}/approvals`, { status: "pending" }),
    enabled: trip?.status === "awaiting_approval",
  });

  // Status transition cache invalidation
  const prevStatusRef = useRef<string | undefined>();
  useEffect(() => {
    const prev = prevStatusRef.current;
    const curr = trip?.status;
    prevStatusRef.current = curr;
    if (!prev || prev === curr) return;
    if (curr === "planned" || curr === "awaiting_approval") {
      // Generation rebuilds itinerary, hotels and weather — refetch all of them, not
      // just the itinerary, so the (re)selected hotel and forecast aren't left stale
      // (the hotels query often resolves empty mid-generation and would never refresh).
      queryClient.invalidateQueries({ queryKey: ["itinerary", tripId] });
      queryClient.invalidateQueries({ queryKey: ["hotels", tripId] });
      queryClient.invalidateQueries({ queryKey: ["weather", tripId] });
    }
    if (curr === "awaiting_approval") {
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
    }
  }, [trip?.status, queryClient, tripId]);

  // ── Share ─────────────────────────────────────────────────────────────────────

  const [shareLoading, setShareLoading] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  async function handleShare() {
    if (!trip) return;
    setShareLoading(true);
    try {
      let token = trip.share_token;
      if (!token) {
        const updated = await api.createShareLink(trip.id);
        token = updated.share_token;
        queryClient.setQueryData(["trip", tripId], updated);
      }
      const url = `${window.location.origin}/share/${token}`;
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2500);
    } finally {
      setShareLoading(false);
    }
  }

  // ── Edit ──────────────────────────────────────────────────────────────────────

  const [editOpen, setEditOpen] = useState(false);

  async function handleEditSave(updates: TripUpdate) {
    const updated = await api.updateTrip(tripId as string, updates);
    queryClient.setQueryData(["trip", tripId], updated);
  }

  // ── Delete ────────────────────────────────────────────────────────────────────

  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.deleteTrip(tripId as string);
      router.replace("/trips");
    } finally {
      setDeleting(false);
    }
  }

  // ── Calendar export ───────────────────────────────────────────────────────────

  const [calendarOpen, setCalendarOpen] = useState(false);
  const [icsLoading, setIcsLoading] = useState(false);

  function handleGoogleCalendar() {
    if (!trip) return;
    const start = trip.start_date.replace(/-/g, "");
    const end = trip.end_date.replace(/-/g, "");
    const url = new URL("https://calendar.google.com/calendar/render");
    url.searchParams.set("action", "TEMPLATE");
    url.searchParams.set("text", `Trip to ${trip.destination_city}`);
    url.searchParams.set("dates", `${start}/${end}`);
    url.searchParams.set("details", `AI-planned itinerary by TravelOS`);
    url.searchParams.set("location", [trip.destination_city, trip.destination_country].filter(Boolean).join(", "));
    window.open(url.toString(), "_blank", "noopener,noreferrer");
    setCalendarOpen(false);
  }

  async function handleDownloadIcs() {
    if (!trip || icsLoading) return;
    setIcsLoading(true);
    try {
      await api.downloadCalendarIcs(trip.id, trip.destination_city);
    } finally {
      setIcsLoading(false);
      setCalendarOpen(false);
    }
  }

  // ── Generate ─────────────────────────────────────────────────────────────────

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    try {
      await api.post(`/api/v1/trips/${tripId}/itinerary/generate`);
      // Record start time so AgentProgress can drive time-based step progress.
      sessionStorage.setItem(genStartKey(tripId as string), String(Date.now()));
      // Optimistically flip to "generating" so the trip query's refetchInterval starts
      // polling and the status-transition effect refreshes the itinerary once the worker
      // finishes. An immediate refetch can race and read the stale "planned" status,
      // which would leave polling off and the UI stuck on the old plan.
      queryClient.setQueryData<TripOut>(["trip", tripId], (old) => (old ? { ...old, status: "generating" } : old));
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

  async function handleDecision(approvalId: string, decision: "approved" | "rejected", resolutionNote?: string) {
    try {
      await api.post(`/api/v1/approvals/${approvalId}`, { decision, ...(resolutionNote ? { resolution_note: resolutionNote } : {}) });
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
      queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
      queryClient.invalidateQueries({ queryKey: ["itinerary", tripId] });
    } catch {
      // silently ignore — stale UI will auto-refresh on next poll
    }
  }

  // ── Replace ───────────────────────────────────────────────────────────────────

  const [replaceTarget, setReplaceTarget] = useState<string | null>(null);
  const [replaceTitle, setReplaceTitle] = useState("");
  const [replaceLoading, setReplaceLoading] = useState(false);

  async function handleReplace(itemId: string) {
    const title = replaceTitle.trim();
    if (!title || replaceLoading) return;
    setReplaceLoading(true);
    try {
      await api.post(`/api/v1/trips/${tripId}/approvals`, { item_id: itemId, replacement_title: title });
      setReplaceTarget(null);
      setReplaceTitle("");
      queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
      queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
    } catch {
      // leave form open on error
    } finally {
      setReplaceLoading(false);
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────────

  const [sidebarTab, setSidebarTab] = useState<"concierge" | "map">("concierge");
  const [chatOpen, setChatOpen] = useState(false);
  const [eventCategory, setEventCategory] = useState("All");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function sendMessage(userText: string): Promise<void> {
    try {
      const res = await api.post<ChatResponse>(`/api/v1/trips/${tripId}/chat`, { question: userText });
      setChatMessages((prev) => [...prev, { role: "assistant", text: res.answer, sources: res.sources }]);
      if (res.proposal_id) {
        queryClient.invalidateQueries({ queryKey: ["trip", tripId] });
        queryClient.invalidateQueries({ queryKey: ["approvals", tripId, "pending"] });
      }
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", text: "Sorry, I couldn't answer that right now. Please try again." }]);
    }
  }

  function askSuggestion(q: string) {
    setChatMessages((prev) => [...prev, { role: "user", text: q }]);
    setChatLoading(true);
    sendMessage(q).finally(() => setChatLoading(false));
  }

  async function handleChatSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", text: q }]);
    setChatLoading(true);
    try {
      await sendMessage(q);
    } finally {
      setChatLoading(false);
    }
  }

  function handleAskConcierge() {
    setSidebarTab("concierge");
    setChatOpen(true);
  }

  // ── Day navigation via IntersectionObserver ────────────────────────────────

  const [activeDay, setActiveDay] = useState(1);
  const daySectionRefs = useRef<Record<number, HTMLElement | null>>({});

  const setDaySectionRef = useCallback(
    (day: number) => (el: HTMLElement | null) => {
      daySectionRefs.current[day] = el;
    },
    [],
  );

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const day = Number((entry.target as HTMLElement).dataset.day);
            if (day) setActiveDay(day);
          }
        }
      },
      { threshold: 0.4 },
    );

    const refs = daySectionRefs.current;
    Object.values(refs).forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, [items]);

  function scrollToDay(day: number) {
    daySectionRefs.current[day]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ── Derived values ────────────────────────────────────────────────────────────

  const nights = trip ? Math.ceil((new Date(trip.end_date).getTime() - new Date(trip.start_date).getTime()) / (1000 * 60 * 60 * 24)) : 0;

  const itemsByDay = items.reduce<Record<number, ItineraryItemOut[]>>((acc, item) => {
    (acc[item.day_number] ??= []).push(item);
    return acc;
  }, {});

  const dayNumbers = Object.keys(itemsByDay)
    .map(Number)
    .sort((a, b) => a - b);

  const pinnedItems = items.filter((i) => i.latitude != null && i.longitude != null);

  const selectedHotel = hotels.find((h) => h.is_selected);
  const otherHotels = hotels.filter((h) => !h.is_selected && (h.price_total != null || h.price_per_night != null));

  const budgetSlices: { label: string; value: number; color: string }[] = (() => {
    const byCategory = trip?.budget_state?.by_category;
    if (byCategory) {
      return [
        { label: "Flights", value: byCategory.flights ?? 0, color: BUDGET_COLORS.Flights },
        { label: "Lodging", value: byCategory.lodging ?? 0, color: BUDGET_COLORS.Lodging },
        { label: "Activities", value: byCategory.activities ?? 0, color: BUDGET_COLORS.Activities },
        { label: "Meals", value: byCategory.meals ?? 0, color: BUDGET_COLORS.Meals },
        { label: "Transport", value: byCategory.transport ?? 0, color: BUDGET_COLORS.Transport },
      ].filter((s) => s.value > 0);
    }
    // Derive from fetched data — convert all costs to the trip's budget currency
    const bc = trip?.budget_currency ?? "INR";
    const toCurrency = (amount: number, from: string | null | undefined): number => convertToBudgetCurrency(amount, from ?? bc, bc);
    const sumConverted = (subset: typeof items) => subset.reduce((s, i) => s + toCurrency(i.est_cost ?? 0, i.est_cost_currency), 0);
    const hotelCost =
      selectedHotel?.price_total != null
        ? toCurrency(selectedHotel.price_total, selectedHotel.price_currency)
        : sumConverted(items.filter((i) => i.item_type === "lodging"));
    const lodging = hotelCost;
    const activities = sumConverted(items.filter((i) => i.item_type === "activity"));
    const meals = sumConverted(items.filter((i) => i.item_type === "meal"));
    const transport = sumConverted(items.filter((i) => i.item_type === "transport"));
    const flightCost = selectedFlight != null ? toCurrency(selectedFlight.price_total, selectedFlight.price_currency) : 0;
    return [
      { label: "Flights", value: flightCost, color: BUDGET_COLORS.Flights },
      { label: "Lodging", value: lodging, color: BUDGET_COLORS.Lodging },
      { label: "Activities", value: activities, color: BUDGET_COLORS.Activities },
      { label: "Meals", value: meals, color: BUDGET_COLORS.Meals },
      { label: "Transport", value: transport, color: BUDGET_COLORS.Transport },
    ].filter((s) => s.value > 0);
  })();

  const budgetDerivedTotal = budgetSlices.reduce((s, d) => s + d.value, 0);
  const budgetDeviationPct: number | null =
    trip?.budget_state?.deviation_pct ??
    (trip?.budget_total && budgetDerivedTotal > 0 ? ((budgetDerivedTotal - trip.budget_total) / trip.budget_total) * 100 : null);
  const budgetCurrency = trip?.budget_state?.currency ?? trip?.budget_currency ?? "INR";
  const budgetStateTotal = trip?.budget_state?.total_planned ?? (budgetDerivedTotal > 0 ? budgetDerivedTotal : null);
  // Major categories with no real price were excluded from total_planned, so "% vs
  // budget" would be misleading. Backend sends missing_categories; legacy trips
  // (generated before that field existed) fall back to inferring from zero values.
  const budgetMissing: string[] =
    trip?.budget_state?.missing_categories ??
    (trip?.budget_state?.by_category
      ? (["flights", "lodging"] as const).filter((k) => !((trip.budget_state?.by_category?.[k] ?? 0) > 0))
      : []);

  const displayEvents = tripEvents.filter((ev) => ev.approval_status !== "rejected");
  const eventCategories = ["All", ...Array.from(new Set(displayEvents.map((ev) => ev.category).filter(Boolean)))];
  const filteredEvents = eventCategory === "All" ? displayEvents : displayEvents.filter((ev) => ev.category === eventCategory);

  const showMapTab = trip?.latitude != null && (pinnedItems.length > 0 || selectedHotel?.latitude != null);

  // ── Early returns ─────────────────────────────────────────────────────────────

  if (!_hasHydrated) return null;

  if (tripLoading) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <p className="text-ink-400 text-sm">Loading trip…</p>
        </div>
      </div>
    );
  }

  if (!trip) {
    return (
      <div className="min-h-screen bg-paper flex flex-col items-center justify-center gap-4">
        <AlertCircle className="w-12 h-12 text-danger" />
        <p className="text-ink-400 text-sm">Trip not found.</p>
        <Link href="/trips">
          <Button size="sm">Back to trips</Button>
        </Link>
      </div>
    );
  }

  // ── State A: Generating ────────────────────────────────────────────────────────

  if (trip.status === "generating") {
    return (
      <div className="min-h-screen bg-paper">
        <NavBar />
        <main className="relative z-10 max-w-2xl mx-auto px-4 pt-28 pb-16">
          <Link href="/trips" className="inline-flex items-center gap-1.5 text-xs text-ink-400 hover:text-ink-900 transition-colors mb-8">
            <ChevronRight className="w-3 h-3 rotate-180" />
            My trips
          </Link>

          <div className="mb-6 flex items-center gap-3">
            <h1 className="font-display text-2xl font-medium text-ink-900 flex-1">{trip.title}</h1>
            <StatusBadge status={trip.status} />
          </div>

          <AgentProgress tripId={tripId as string} />
        </main>
      </div>
    );
  }

  // ── State B: Awaiting Approval ─────────────────────────────────────────────────

  if (trip.status === "awaiting_approval" && pendingApprovals.length > 0) {
    return (
      <div className="min-h-screen bg-paper">
        <NavBar />

        {/* Sticky approval banner */}
        <div className="sticky top-16 z-40 border-b border-danger/20 bg-danger-tint">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
            <AlertCircle className="w-4 h-4 text-danger shrink-0" />
            <p className="text-sm text-danger font-medium flex-1">
              {pendingApprovals.length} change{pendingApprovals.length !== 1 ? "s" : ""} need{pendingApprovals.length === 1 ? "s" : ""} your
              review
            </p>
            <span className="text-xs text-danger/80">Scroll down to review</span>
          </div>
        </div>

        <main className="relative z-10 max-w-2xl mx-auto px-4 pt-8 pb-24">
          <Link href="/trips" className="inline-flex items-center gap-1.5 text-xs text-ink-400 hover:text-ink-900 transition-colors mb-6">
            <ChevronRight className="w-3 h-3 rotate-180" />
            My trips
          </Link>

          <div className="mb-8 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <h1 className="font-display text-2xl font-medium text-ink-900 truncate">{trip.title}</h1>
              <p className="text-sm text-ink-400 mt-0.5">
                {trip.destination_city}
                {trip.destination_country ? `, ${trip.destination_country}` : ""} · {nights} night{nights !== 1 ? "s" : ""}
              </p>
            </div>
            <StatusBadge status={trip.status} className="shrink-0" />
          </div>

          <div className="space-y-3">
            {pendingApprovals.map((a, i) => (
              <motion.div key={a.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}>
                <ApprovalCard approval={a} onDecision={handleDecision} />
              </motion.div>
            ))}
          </div>
        </main>
      </div>
    );
  }

  // ── State C: Planned / Default ─────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-paper">
      <NavBar />

      <TripHero
        trip={trip}
        weatherDays={weatherDays}
        onShare={handleShare}
        shareLoading={shareLoading}
        shareCopied={shareCopied}
        calendarOpen={calendarOpen}
        onToggleCalendar={() => setCalendarOpen((v) => !v)}
        onGoogleCalendar={handleGoogleCalendar}
        onDownloadIcs={handleDownloadIcs}
        icsLoading={icsLoading}
        onEdit={() => setEditOpen(true)}
        onDeleteClick={() => setDeleteConfirm(true)}
      />

      {/* Planning status / generate banner */}
      {(trip.status === "planning" || trip.status === "failed") && (
        <div className="max-w-7xl mx-auto px-4 pt-6">
          <Card className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-5">
            <div className="w-12 h-12 rounded-xl bg-sunset flex items-center justify-center shrink-0 shadow-glow">
              <Sparkles className="w-6 h-6 text-[#1F1206]" />
            </div>
            <div className="flex-1 min-w-0">
              {trip.status === "failed" ? (
                <>
                  <p className="text-sm font-medium text-danger mb-0.5">Generation failed</p>
                  {generateError && <p className="text-xs text-ink-400">{generateError}</p>}
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-ink-900 mb-0.5">No itinerary yet</p>
                  <p className="text-xs text-ink-400">Let TravelOS AI agents plan everything for you.</p>
                </>
              )}
            </div>
            <Button onClick={handleGenerate} loading={generating} iconLeft={Sparkles} className="w-full sm:w-auto whitespace-nowrap">
              {generating ? "Queuing…" : trip.status === "failed" ? "Try again" : "Generate itinerary"}
            </Button>
          </Card>
        </div>
      )}

      {/* Main layout */}
      <div className="max-w-7xl mx-auto px-4 pt-8 pb-32">
        <div className="flex gap-6 lg:gap-8 relative">
          <SectionNav
            days={dayNumbers}
            activeDay={activeDay}
            onSelectDay={scrollToDay}
            showHotelsLink={hotels.length > 0}
            showBudgetLink={budgetSlices.length > 0}
            showEventsLink={trip.status === "planned"}
            showPackingLink={!!trip.packing_list}
          />

          {/* Center: main content */}
          <div className="flex-1 min-w-0 space-y-8">
            {budgetSlices.length > 0 && (
              <BudgetPanel
                slices={budgetSlices}
                currency={budgetCurrency}
                deviationPct={budgetDeviationPct}
                budgetTotal={trip.budget_total}
                stateTotal={budgetStateTotal}
                missingCategories={budgetMissing}
              />
            )}

            <ItinerarySection
              dayNumbers={dayNumbers}
              itemsByDay={itemsByDay}
              weatherDays={weatherDays}
              budgetCurrency={trip.budget_currency}
              tripStatus={trip.status}
              onRegenerate={handleGenerate}
              regenerating={generating}
              setDaySectionRef={setDaySectionRef}
              onAskConcierge={handleAskConcierge}
              replaceTarget={replaceTarget}
              replaceTitle={replaceTitle}
              setReplaceTitle={setReplaceTitle}
              replaceLoading={replaceLoading}
              onReplaceTargetToggle={(itemId) => {
                setReplaceTitle("");
                setReplaceTarget(replaceTarget === itemId ? null : itemId);
              }}
              onReplaceSubmit={handleReplace}
              onReplaceCancel={() => setReplaceTarget(null)}
            />
            {dayNumbers.length === 0 && <EmptyItineraryState tripStatus={trip.status} />}

            {hotels.length > 0 && (
              <HotelsPanel
                selectedHotel={selectedHotel}
                otherHotels={otherHotels}
                onSelectHotel={async (hotelId) => {
                  const updated = await api.selectHotel(tripId as string, hotelId);
                  queryClient.setQueryData(["hotels", tripId], updated);
                }}
              />
            )}

            {trip.status !== "planning" && (
              <FlightsPanel
                flightOrigin={flightOrigin}
                setFlightOrigin={setFlightOrigin}
                flightSearch={flightSearch}
                onSearch={() => {
                  if (flightOrigin.trim().length === 3) setFlightSearch(flightOrigin.trim().toUpperCase());
                }}
                flights={flights}
                flightsFetching={flightsFetching}
                selectedFlight={selectedFlight}
                setSelectedFlight={setSelectedFlight}
              />
            )}

            {(trip.status === "planned" || trip.status === "awaiting_approval") && (
              <EventsPanel
                events={filteredEvents}
                totalCount={displayEvents.length}
                categories={eventCategories}
                activeCategory={eventCategory}
                onCategoryChange={setEventCategory}
              />
            )}

            <PackingList packingList={trip.packing_list} />
          </div>

          {/* Right sidebar — Map / AI Concierge */}
          <div className="hidden xl:flex flex-col w-[320px] shrink-0">
            <div className="sticky top-24 flex flex-col gap-3" style={{ height: "calc(100vh - 7rem)" }}>
              <Tabs
                tabs={[
                  { id: "concierge", label: "AI Concierge", icon: Compass },
                  ...(showMapTab ? [{ id: "map", label: "Map", icon: MapPin }] : []),
                ]}
                active={sidebarTab}
                onChange={(id) => setSidebarTab(id as "concierge" | "map")}
                className="shrink-0"
              />

              <AnimatePresence mode="wait">
                {sidebarTab === "concierge" && (
                  <motion.div
                    key="concierge-sidebar"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                    className="flex-1 min-h-0 flex flex-col"
                  >
                    <ConciergeThread
                      destinationCity={trip.destination_city}
                      messages={chatMessages}
                      input={chatInput}
                      onInputChange={setChatInput}
                      onSubmit={handleChatSubmit}
                      loading={chatLoading}
                      chatEndRef={chatEndRef}
                      onSuggestionClick={askSuggestion}
                    />
                  </motion.div>
                )}

                {sidebarTab === "map" && (
                  <motion.div
                    key="map-sidebar"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                    className="flex-1 min-h-0 flex flex-col"
                  >
                    <MapCard
                      destinationCity={trip.destination_city}
                      pinnedItems={pinnedItems}
                      centerLat={trip.latitude}
                      centerLng={trip.longitude}
                      selectedHotel={selectedHotel}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Concierge (mobile only) */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3 xl:hidden">
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="relative w-[360px] max-w-[calc(100vw-2rem)] flex flex-col shadow-overlay rounded-xl"
              style={{ height: "50vh", maxHeight: "480px" }}
            >
              <button
                onClick={() => setChatOpen(false)}
                className="absolute top-3 right-3 z-10 text-ink-400 hover:text-ink-900 bg-surface-raised border border-ink-900/10 rounded-full p-1"
              >
                <X className="w-4 h-4" />
              </button>
              <ConciergeThread
                destinationCity={trip.destination_city}
                messages={chatMessages}
                input={chatInput}
                onInputChange={setChatInput}
                onSubmit={handleChatSubmit}
                loading={chatLoading}
                chatEndRef={chatEndRef}
                onSuggestionClick={askSuggestion}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          whileTap={{ y: 1 }}
          onClick={() => setChatOpen((v) => !v)}
          className={`flex items-center gap-2 px-5 py-3 rounded-xl font-medium text-sm transition-shadow ${
            chatOpen ? "bg-surface-raised text-ink-900 border border-ink-900/10 shadow-lift" : "bg-sunset text-[#1F1206] shadow-glow"
          }`}
        >
          <Compass className="w-4 h-4" />
          {chatOpen ? "Close" : "Ask AI"}
          {!chatOpen && pendingApprovals.length > 0 && <span className="w-2 h-2 rounded-full bg-danger" />}
        </motion.button>
      </div>

      <EditTripModal open={editOpen} trip={trip} onClose={() => setEditOpen(false)} onSave={handleEditSave} />

      <Modal
        open={deleteConfirm}
        onClose={() => setDeleteConfirm(false)}
        width="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteConfirm(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} loading={deleting}>
              Delete
            </Button>
          </>
        }
      >
        <h3 className="font-display text-base font-medium text-ink-900 mb-1">Delete trip?</h3>
        <p className="text-sm text-ink-400">
          This will permanently remove <span className="text-ink-900">{trip.title}</span> and all its itinerary data. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
