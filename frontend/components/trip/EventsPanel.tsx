import { CalendarDays } from "lucide-react";
import type { TripEventOut } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";

export function EventsPanel({
  events,
  totalCount,
  categories,
  activeCategory,
  onCategoryChange,
}: {
  events: TripEventOut[];
  totalCount: number;
  categories: string[];
  activeCategory: string;
  onCategoryChange: (cat: string) => void;
}) {
  return (
    <section id="events-section">
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 rounded-lg bg-accent-tint flex items-center justify-center">
            <CalendarDays className="w-3.5 h-3.5 text-accent" />
          </div>
          <h2 className="text-sm font-medium text-ink-900">Local Events &amp; Shows</h2>
          {totalCount > 0 && (
            <span className="ml-auto text-[10px] font-mono text-ink-400">
              {events.length}/{totalCount} events
            </span>
          )}
        </div>

        {/* Category filter pills */}
        {categories.length > 1 && (
          <div className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-hide mb-4">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => onCategoryChange(cat)}
                className={`shrink-0 text-[10px] font-medium px-3 py-1.5 rounded-full border transition-colors ${
                  activeCategory === cat
                    ? "bg-accent-tint border-accent/30 text-accent"
                    : "bg-surface border-ink-900/10 text-ink-400 hover:text-ink-600 hover:border-ink-900/20"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        )}

        {events.length > 0 ? (
          <div className="space-y-3">
            {events.map((ev) => (
              <div key={ev.id} className="rounded-lg p-3 border border-ink-900/10 hover:border-ink-900/20 transition-colors">
                <div className="flex items-start gap-3">
                  {ev.image_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={ev.image_url} alt="" className="w-14 h-14 rounded-lg object-cover shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <p className="text-xs font-medium text-ink-900 truncate">{ev.event_name}</p>
                      <Badge tone={ev.source === "ticketmaster" ? "info" : "warning"}>
                        {ev.source === "ticketmaster" ? "Ticketmaster" : "Eventbrite"}
                      </Badge>
                    </div>
                    <p className="text-[10px] text-ink-400 mb-1 font-mono">
                      {ev.venue_name}
                      {ev.event_date && ` · ${new Date(ev.event_date).toLocaleDateString("en", { month: "short", day: "numeric" })}`}
                      {ev.start_time && ` · ${ev.start_time.slice(0, 5)}`}
                    </p>
                    <div className="flex items-center gap-2 flex-wrap">
                      {ev.category && (
                        <span className="text-[9px] text-accent bg-accent-tint px-1.5 py-0.5 rounded-full">{ev.category}</span>
                      )}
                      {ev.price_min != null && (
                        <span className="text-[9px] text-ink-400 font-mono">
                          {ev.price_currency ?? ""} {ev.price_min === 0 ? "Free" : `from ${ev.price_min}`}
                        </span>
                      )}
                      {ev.url && (
                        <a
                          href={ev.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[9px] text-accent hover:text-accent-deep transition-colors ml-auto"
                        >
                          Tickets →
                        </a>
                      )}
                    </div>
                  </div>
                </div>
                {ev.summary && (
                  <p className="text-[10px] text-ink-400 mt-2 leading-relaxed border-t border-ink-900/10 pt-2">{ev.summary}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={CalendarDays}
            title={activeCategory === "All" ? "No events found for your dates" : `No ${activeCategory} events found`}
            body="The events agent searches Ticketmaster and Eventbrite for concerts, comedy shows, theatre, sports and more during your trip."
          />
        )}
      </Card>
    </section>
  );
}
