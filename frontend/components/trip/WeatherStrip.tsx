import { Sun, CloudRain, Wind, Zap } from "lucide-react";
import type { WeatherDay } from "@/lib/api";

export function WeatherIcon({ code, adverse }: { code: number; adverse: boolean }) {
  if (adverse || code >= 60) return <CloudRain className="w-4 h-4 text-info" />;
  if (code >= 40) return <Wind className="w-4 h-4 text-ink-400" />;
  if (code >= 1) return <Zap className="w-4 h-4 text-warning" />;
  return <Sun className="w-4 h-4 text-warning" />;
}

export function WeatherTimeline({ days, heroStyle = false }: { days: WeatherDay[]; heroStyle?: boolean }) {
  if (!days.length) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-0.5 scrollbar-hide">
      {days.slice(0, 7).map((d) => (
        <div
          key={d.date}
          className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl shrink-0 ${
            heroStyle
              ? d.is_adverse
                ? "bg-danger/40 border border-white/30"
                : "bg-black/25 border border-white/20"
              : d.is_adverse
                ? "bg-danger-tint"
                : "bg-ink-100"
          }`}
        >
          <span className={`text-[10px] ${heroStyle ? "text-white/70" : "text-ink-400"}`}>
            {new Date(d.date + "T00:00:00").toLocaleDateString("en-US", { weekday: "short" })}
          </span>
          <WeatherIcon code={d.condition_code} adverse={d.is_adverse} />
          <span className={`font-mono text-[10px] ${heroStyle ? "text-white/90 font-medium" : "text-ink-600"}`}>
            {Math.round(d.temp_max_c)}°
          </span>
        </div>
      ))}
    </div>
  );
}
