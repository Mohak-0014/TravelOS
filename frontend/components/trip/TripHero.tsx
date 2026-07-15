"use client";

import Link from "next/link";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import {
  ChevronRight,
  MapPin,
  Calendar,
  Users,
  DollarSign,
  Share2,
  Check,
  Loader2,
  CalendarPlus,
  CalendarDays,
  Download,
  Pencil,
  Trash2,
} from "lucide-react";
import type { TripOut, WeatherDay } from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { WeatherTimeline } from "./WeatherStrip";

export function TripHero({
  trip,
  weatherDays,
  onShare,
  shareLoading,
  shareCopied,
  calendarOpen,
  onToggleCalendar,
  onGoogleCalendar,
  onDownloadIcs,
  icsLoading,
  onEdit,
  onDeleteClick,
}: {
  trip: TripOut;
  weatherDays: WeatherDay[];
  onShare: () => void;
  shareLoading: boolean;
  shareCopied: boolean;
  calendarOpen: boolean;
  onToggleCalendar: () => void;
  onGoogleCalendar: () => void;
  onDownloadIcs: () => void;
  icsLoading: boolean;
  onEdit: () => void;
  onDeleteClick: () => void;
}) {
  const { scrollY } = useScroll();
  const heroBgY = useTransform(scrollY, [0, 300], [0, 90]);

  return (
    <div className="relative h-56 overflow-hidden">
      {/* Parallax background layer */}
      <motion.div
        style={{
          y: heroBgY,
          ...(trip.cover_image_url
            ? { backgroundImage: `url(${trip.cover_image_url})`, backgroundSize: "cover", backgroundPosition: "center" }
            : {}),
        }}
        className={`absolute -top-24 inset-x-0 bottom-0 ${!trip.cover_image_url ? "bg-ink-100 noise" : ""}`}
      />
      {/* Overlay — heavier when photo is present for text legibility */}
      {trip.cover_image_url ? (
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/45 to-black/10" />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent" />
      )}

      {/* Hero content */}
      <div className="relative z-10 h-full flex flex-col justify-end px-4 pb-5 max-w-7xl mx-auto">
        <Link
          href="/trips"
          className="absolute top-5 left-4 inline-flex items-center gap-1.5 text-xs text-white/60 hover:text-white transition-colors"
        >
          <ChevronRight className="w-3 h-3 rotate-180" />
          My trips
        </Link>

        <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <MapPin className="w-4 h-4 text-white/70" />
              <span className="text-white/70 text-xs font-mono uppercase tracking-widest">{trip.destination_country ?? ""}</span>
            </div>
            <h1 className="font-display text-3xl lg:text-4xl font-medium text-white leading-tight">{trip.destination_city}</h1>
          </div>

          <div className="flex flex-col gap-2 lg:items-end">
            {/* Trip meta pills */}
            <div className="flex flex-wrap gap-2">
              <div className="flex items-center gap-1.5 text-xs font-mono text-white/80 bg-black/25 px-3 py-1.5 rounded-full border border-white/20">
                <Calendar className="w-3 h-3" />
                {new Date(trip.start_date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })} –{" "}
                {new Date(trip.end_date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </div>
              <div className="flex items-center gap-1.5 text-xs font-mono text-white/80 bg-black/25 px-3 py-1.5 rounded-full border border-white/20">
                <Users className="w-3 h-3" />
                {trip.num_travelers} traveler{trip.num_travelers !== 1 ? "s" : ""}
              </div>
              {trip.budget_total && (
                <div className="flex items-center gap-1.5 text-xs font-mono text-white/80 bg-black/25 px-3 py-1.5 rounded-full border border-white/20">
                  <DollarSign className="w-3 h-3" />
                  {trip.budget_currency} {trip.budget_total.toLocaleString()}
                </div>
              )}
              <StatusBadge status={trip.status} className="!bg-black/25 !text-white border border-white/20" />

              <button
                onClick={onShare}
                disabled={shareLoading}
                className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/15 transition-colors disabled:opacity-50"
                title="Copy share link"
              >
                {shareLoading ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : shareCopied ? (
                  <Check className="w-3 h-3 text-success" />
                ) : (
                  <Share2 className="w-3 h-3" />
                )}
                {shareCopied ? "Copied!" : "Share"}
              </button>

              {/* Calendar export */}
              <div className="relative">
                <button
                  onClick={onToggleCalendar}
                  className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/15 transition-colors"
                  title="Export to calendar"
                >
                  <CalendarPlus className="w-3 h-3" />
                  Calendar
                </button>
                <AnimatePresence>
                  {calendarOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 6, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 6, scale: 0.96 }}
                      transition={{ duration: 0.15 }}
                      className="absolute top-full mt-2 left-0 w-44 bg-surface border border-ink-900/10 rounded-lg shadow-overlay py-1 z-20"
                    >
                      <button
                        onClick={onGoogleCalendar}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-ink-600 hover:bg-ink-900/[0.03] transition-colors"
                      >
                        <CalendarDays className="w-3.5 h-3.5 text-accent shrink-0" />
                        Google Calendar
                      </button>
                      <button
                        onClick={onDownloadIcs}
                        disabled={icsLoading}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-ink-600 hover:bg-ink-900/[0.03] transition-colors disabled:opacity-50"
                      >
                        {icsLoading ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                        ) : (
                          <Download className="w-3.5 h-3.5 text-accent shrink-0" />
                        )}
                        Download .ics
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <button
                onClick={onEdit}
                className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 px-3 py-1.5 rounded-full border border-white/20 hover:bg-white/15 transition-colors"
                title="Edit trip"
              >
                <Pencil className="w-3 h-3" />
                Edit
              </button>

              <button
                onClick={onDeleteClick}
                className="flex items-center gap-1.5 text-xs text-white/80 bg-black/25 px-3 py-1.5 rounded-full border border-white/20 hover:bg-danger/70 hover:text-white hover:border-danger transition-colors"
                title="Delete trip"
              >
                <Trash2 className="w-3 h-3" />
                Delete
              </button>
            </div>

            {weatherDays.length > 0 && (
              <div className="mt-1">
                <WeatherTimeline days={weatherDays} heroStyle />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
