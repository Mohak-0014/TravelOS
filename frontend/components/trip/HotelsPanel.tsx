import { motion } from "framer-motion";
import { Star, MapPin } from "lucide-react";
import type { HotelCandidateOut } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SectionHeader } from "@/components/ui/SectionHeader";

function Stars({ rating, size = "w-3 h-3" }: { rating: number; size?: string }) {
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <Star key={i} className={`${size} ${i < Math.round(rating) ? "text-warning fill-warning" : "text-ink-200"}`} />
      ))}
    </div>
  );
}

export function HotelsPanel({
  selectedHotel,
  otherHotels,
  onSelectHotel,
}: {
  selectedHotel: HotelCandidateOut | undefined;
  otherHotels: HotelCandidateOut[];
  onSelectHotel: (hotelId: string) => void;
}) {
  return (
    <motion.section
      id="hotels-section"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
    >
      <SectionHeader eyebrow="Hotels" />

      <div className="space-y-3">
        {/* Selected hotel — prominent */}
        {selectedHotel && (
          <Card className="border-accent/30">
            <div className="flex items-start justify-between gap-4 mb-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge tone="accent">Selected</Badge>
                  {selectedHotel.refundable != null && (
                    <Badge tone={selectedHotel.refundable ? "success" : "danger"}>
                      {selectedHotel.refundable ? "Refundable" : "Non-refundable"}
                    </Badge>
                  )}
                </div>
                <p className="font-medium text-ink-900 text-base leading-snug">{selectedHotel.name}</p>
                {selectedHotel.star_rating != null && (
                  <div className="flex items-center gap-1 mt-0.5">
                    <Stars rating={selectedHotel.star_rating} />
                    <span className="text-xs text-ink-400 ml-1">{selectedHotel.star_rating.toFixed(1)}</span>
                  </div>
                )}
                {selectedHotel.address && (
                  <p className="text-xs text-ink-400 mt-1 flex items-center gap-1">
                    <MapPin className="w-3 h-3 shrink-0" />
                    {selectedHotel.address}
                  </p>
                )}
                {selectedHotel.meal_plan && (
                  <span className="inline-block mt-2 text-[10px] text-ink-400 bg-ink-100 px-2 py-0.5 rounded-full">
                    {selectedHotel.meal_plan}
                  </span>
                )}
              </div>

              {(selectedHotel.price_per_night != null || selectedHotel.price_total != null) && (
                <div className="text-right shrink-0 font-mono">
                  {selectedHotel.price_per_night != null && (
                    <p className="text-lg font-medium text-ink-900 tabular-nums">
                      {selectedHotel.price_currency ?? ""} {selectedHotel.price_per_night.toLocaleString()}
                      <span className="text-xs font-normal text-ink-400">/night</span>
                    </p>
                  )}
                  {selectedHotel.price_total != null && (
                    <p className="text-xs text-ink-400 tabular-nums mt-0.5">
                      {selectedHotel.price_currency ?? ""} {selectedHotel.price_total.toLocaleString()} total
                    </p>
                  )}
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Other hotel candidates */}
        {otherHotels.map((hotel, hidx) => (
          <motion.div
            key={hotel.id}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: hidx * 0.07, duration: 0.35 }}
            whileHover={{ y: -2 }}
          >
            <Card>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-ink-600 text-sm">{hotel.name}</p>
                  {hotel.star_rating != null && <Stars rating={hotel.star_rating} size="w-2.5 h-2.5" />}
                  {hotel.address && <p className="text-xs text-ink-300 truncate mt-0.5">{hotel.address}</p>}
                  <div className="flex items-center gap-2 mt-1.5">
                    {hotel.meal_plan && (
                      <span className="text-[10px] text-ink-400 bg-ink-100 px-1.5 py-0.5 rounded-full">{hotel.meal_plan}</span>
                    )}
                    {hotel.refundable != null && (
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-full ${hotel.refundable ? "text-success bg-success-tint" : "text-danger bg-danger-tint"}`}
                      >
                        {hotel.refundable ? "Refundable" : "Non-refundable"}
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0 flex flex-col items-end gap-2">
                  <div className="font-mono">
                    {hotel.price_per_night != null ? (
                      <>
                        <p className="text-sm font-medium text-ink-600 tabular-nums">
                          {hotel.price_currency ?? ""} {hotel.price_per_night.toLocaleString()}
                          <span className="text-[10px] font-normal text-ink-300">/night</span>
                        </p>
                        {hotel.price_total != null && (
                          <p className="text-[10px] text-ink-300 tabular-nums">
                            {hotel.price_currency ?? ""} {hotel.price_total.toLocaleString()} total
                          </p>
                        )}
                      </>
                    ) : (
                      <p className="text-[11px] text-ink-400 italic">Price on request</p>
                    )}
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => onSelectHotel(hotel.id)}>
                    Set as hotel
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>
    </motion.section>
  );
}
