import { motion } from "framer-motion";
import { ArrowRight, Loader2, PlaneTakeoff } from "lucide-react";
import type { FlightOfferOut } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

function isSameFlight(a: FlightOfferOut, b: FlightOfferOut): boolean {
  return a.origin === b.origin && a.destination === b.destination && a.airline === b.airline && a.price_total === b.price_total;
}

export function FlightsPanel({
  flightOrigin,
  setFlightOrigin,
  flightSearch,
  onSearch,
  flights,
  flightsFetching,
  selectedFlight,
  setSelectedFlight,
}: {
  flightOrigin: string;
  setFlightOrigin: (v: string) => void;
  flightSearch: string;
  onSearch: () => void;
  flights: FlightOfferOut[];
  flightsFetching: boolean;
  selectedFlight: FlightOfferOut | null;
  setSelectedFlight: (f: FlightOfferOut | null) => void;
}) {
  return (
    <motion.section id="flights-section" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 rounded-lg bg-accent-tint flex items-center justify-center">
            <PlaneTakeoff className="w-3.5 h-3.5 text-accent" />
          </div>
          <h2 className="text-sm font-medium text-ink-900">Flight Prices</h2>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSearch();
          }}
          className="flex gap-2 mb-4"
        >
          <Input
            type="text"
            value={flightOrigin}
            onChange={(e) => setFlightOrigin(e.target.value.toUpperCase().slice(0, 3))}
            placeholder="Your airport (e.g. DEL)"
            maxLength={3}
            className="text-xs h-9 flex-1 uppercase tracking-widest font-mono"
          />
          <Button type="submit" size="sm" disabled={flightOrigin.length !== 3 || flightsFetching}>
            {flightsFetching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}
          </Button>
        </form>

        {flightSearch && !flightsFetching && flights.length === 0 && (
          <p className="text-xs text-ink-400 text-center py-4">
            No flights found from {flightSearch} — check your airport code or try again later.
          </p>
        )}

        {flights.length > 0 && (
          <div className="space-y-2">
            {flights.map((f, i) => {
              const selected = selectedFlight != null && isSameFlight(selectedFlight, f);
              return (
                <div
                  key={i}
                  className={`rounded-lg p-3 border transition-colors ${selected ? "border-accent bg-accent-tint" : "border-ink-900/10 hover:border-ink-900/20"}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 font-mono">
                        {selected && (
                          <span className="text-[9px] font-medium text-accent bg-surface-raised px-1.5 py-0.5 rounded-full">Selected</span>
                        )}
                        <span className="text-xs font-medium text-ink-900">{f.origin}</span>
                        <ArrowRight className="w-3 h-3 text-ink-300 shrink-0" />
                        <span className="text-xs font-medium text-ink-900">{f.destination}</span>
                        <span className="text-[9px] text-ink-400 bg-ink-100 px-1.5 py-0.5 rounded-full font-sans">{f.airline}</span>
                      </div>
                      <div className="text-[10px] text-ink-400">
                        {f.duration_outbound}
                        {f.stops_outbound === 0 ? " · nonstop" : ` · ${f.stops_outbound} stop`}
                        {f.duration_return && (
                          <span>
                            {" "}
                            · return {f.duration_return}
                            {f.stops_return === 0 ? " nonstop" : ""}
                          </span>
                        )}
                        <span className="ml-2 text-accent/70">{f.cabin.toLowerCase()}</span>
                      </div>
                    </div>
                    <div className="text-right shrink-0 flex flex-col items-end gap-1.5">
                      <div className="font-mono">
                        <p className="text-sm font-medium text-ink-900">
                          {f.price_currency} {f.price_total.toLocaleString()}
                        </p>
                        <p className="text-[9px] text-ink-400 font-sans">per person</p>
                      </div>
                      <Button size="sm" variant={selected ? "secondary" : "primary"} onClick={() => setSelectedFlight(selected ? null : f)}>
                        {selected ? "Deselect" : "Add to budget"}
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </motion.section>
  );
}
