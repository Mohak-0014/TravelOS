export interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

export function BudgetDonut({ slices, currency }: { slices: DonutSlice[]; currency?: string }) {
  const total = slices.reduce((s, d) => s + d.value, 0);
  if (total === 0) return null;

  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-6">
      <svg width="140" height="140" viewBox="0 0 140 140" className="shrink-0">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="18" />
        {slices.map((slice) => {
          const pct = slice.value / total;
          const dashLen = pct * circumference;
          const thisOffset = offset;
          offset += dashLen;
          return (
            <circle
              key={slice.label}
              cx="70"
              cy="70"
              r={radius}
              fill="none"
              stroke={slice.color}
              strokeWidth="18"
              strokeDasharray={`${dashLen} ${circumference - dashLen}`}
              strokeDashoffset={-thisOffset + circumference * 0.25}
              strokeLinecap="round"
              style={{ transition: "stroke-dasharray 0.6s ease" }}
            />
          );
        })}
        <text x="70" y="65" textAnchor="middle" fontSize="11" fill="#6C7787" fontFamily="inherit">
          Total
        </text>
        <text x="70" y="84" textAnchor="middle" fontSize="13" fill="#F2F5F7" fontWeight="600" fontFamily="inherit">
          {currency ?? ""} {total.toLocaleString()}
        </text>
      </svg>

      <div className="flex flex-col gap-2 min-w-0">
        {slices.map((slice) => (
          <div key={slice.label} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: slice.color }} />
            <span className="text-xs text-ink-400 flex-1">{slice.label}</span>
            <span className="font-mono text-xs text-ink-900 tabular-nums font-medium">
              {currency} {slice.value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
