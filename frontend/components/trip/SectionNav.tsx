import { Hotel, Wallet, CalendarDays, Luggage } from "lucide-react";
import { DayNav } from "./DayNav";

function jumpTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

export function SectionNav({
  days,
  activeDay,
  onSelectDay,
  showHotelsLink,
  showBudgetLink,
  showEventsLink,
  showPackingLink,
}: {
  days: number[];
  activeDay: number;
  onSelectDay: (d: number) => void;
  showHotelsLink: boolean;
  showBudgetLink: boolean;
  showEventsLink: boolean;
  showPackingLink: boolean;
}) {
  if (days.length === 0) return null;

  return (
    <div className="hidden lg:block w-[220px] shrink-0">
      <div className="sticky top-24">
        <DayNav days={days} activeDay={activeDay} onSelect={onSelectDay} />

        <div className="mt-6 space-y-1">
          <p className="font-mono text-[10px] font-medium text-ink-400 uppercase tracking-wider mb-2 px-2">Jump to</p>
          {showHotelsLink && (
            <button
              onClick={() => jumpTo("hotels-section")}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-ink-400 hover:text-ink-900 hover:bg-ink-900/[0.03] transition-colors flex items-center gap-2"
            >
              <Hotel className="w-3 h-3" />
              Hotels
            </button>
          )}
          {showBudgetLink && (
            <button
              onClick={() => jumpTo("budget-section")}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-ink-400 hover:text-ink-900 hover:bg-ink-900/[0.03] transition-colors flex items-center gap-2"
            >
              <Wallet className="w-3 h-3" />
              Budget
            </button>
          )}
          {showEventsLink && (
            <button
              onClick={() => jumpTo("events-section")}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-ink-400 hover:text-ink-900 hover:bg-ink-900/[0.03] transition-colors flex items-center gap-2"
            >
              <CalendarDays className="w-3 h-3" />
              Events
            </button>
          )}
          {showPackingLink && (
            <button
              onClick={() => jumpTo("packing-section")}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-ink-400 hover:text-ink-900 hover:bg-ink-900/[0.03] transition-colors flex items-center gap-2"
            >
              <Luggage className="w-3 h-3" />
              Packing
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
