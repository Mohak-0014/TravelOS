import dynamic from "next/dynamic";
import { Loader2, MapPin } from "lucide-react";
import type { ItineraryItemOut, HotelCandidateOut } from "@/lib/api";

const TripMap = dynamic(() => import("./TripMap"), {
  ssr: false,
  loading: () => (
    <div className="h-full bg-ink-100 animate-pulse flex items-center justify-center">
      <Loader2 className="w-6 h-6 text-accent animate-spin" />
    </div>
  ),
});

const LEGEND: { color: string; label: string }[] = [
  { color: "#D9A05B", label: "Activity" },
  { color: "#FFC46B", label: "Meal" },
  { color: "#3ECF8E", label: "Transport" },
  { color: "#FF9E64", label: "Hotel" },
];

export function MapCard({
  destinationCity,
  pinnedItems,
  centerLat,
  centerLng,
  selectedHotel,
}: {
  destinationCity: string;
  pinnedItems: ItineraryItemOut[];
  centerLat: number | null;
  centerLng: number | null;
  selectedHotel: HotelCandidateOut | undefined;
}) {
  return (
    <div className="flex-1 min-h-0 rounded-xl overflow-hidden border border-ink-900/10 flex flex-col bg-surface">
      {/* Map header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-ink-900/10 shrink-0">
        <div className="w-6 h-6 rounded-md bg-accent-tint flex items-center justify-center shrink-0">
          <MapPin className="w-3 h-3 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-ink-900">{destinationCity}</p>
          <p className="text-[10px] text-ink-400">{pinnedItems.length} places mapped</p>
        </div>
        {selectedHotel && (
          <span className="text-[10px] text-accent bg-accent-tint px-2 py-0.5 rounded-full font-medium shrink-0">Hotel</span>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 min-h-0">
        {centerLat != null && centerLng != null && (
          <TripMap
            items={pinnedItems}
            centerLat={centerLat}
            centerLng={centerLng}
            hotel={
              selectedHotel?.latitude != null && selectedHotel?.longitude != null
                ? { lat: selectedHotel.latitude, lng: selectedHotel.longitude, name: selectedHotel.name }
                : null
            }
            height="100%"
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-t border-ink-900/10 shrink-0">
        {LEGEND.map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
            <span className="text-[9px] text-ink-400">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
