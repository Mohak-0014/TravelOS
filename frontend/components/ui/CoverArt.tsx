import { RouteDash } from "./RouteDash";
import { cn } from "@/lib/ui";

export interface CoverArtProps {
  city: string;
  country?: string | null;
  imageUrl?: string | null;
  height?: string; // Tailwind height class, e.g. "h-64"
  className?: string;
  children?: React.ReactNode;
}

/** Trip cover banner: real photo with an ink scrim for legible overlaid text,
 * or — when no photo is available yet — a neutral field with the destination
 * name and a route-line motif. Pure presentational: no store/api imports, so
 * the auth-less /share page can use it too. Replaces the old destGradient()
 * hash-to-color-band helper that was copy-pasted across three pages. */
export function CoverArt({ city, country, imageUrl, height = "h-64", className, children }: CoverArtProps) {
  return (
    <div className={cn("relative overflow-hidden", height, className)}>
      {imageUrl ? (
        <>
          <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${imageUrl})` }} />
          <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/15 to-transparent" />
        </>
      ) : (
        <div className="absolute inset-0 bg-ink-100 flex flex-col items-center justify-center gap-3 px-8">
          {/* Bare mode (no children): show our own label. As a hero/card
              backdrop (children given), the caller renders its own text, so
              we show only the decorative route motif — never both, or the
              label would double up with the caller's overlay. */}
          {!children && (
            <span className="font-mono text-xs uppercase tracking-[0.2em] text-ink-400">{[city, country].filter(Boolean).join(", ")}</span>
          )}
          <RouteDash arc animate={false} className="w-full max-w-[220px] opacity-70" />
        </div>
      )}
      {children && <div className="relative z-10 h-full">{children}</div>}
    </div>
  );
}
