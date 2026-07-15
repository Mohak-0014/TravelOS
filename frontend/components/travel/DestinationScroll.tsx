"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowUpRight, ChevronLeft, ChevronRight } from "lucide-react";
import { TiltCard } from "@/components/ui/TiltCard";

export interface Destination {
  id: string;
  name: string;
  country: string;
  coords: string;
  /** Unsplash photo (public CDN). Cards gracefully fall back to the gradient
   * below while it loads or if it fails — never a broken tile. */
  photo: string;
  from: string;
  to: string;
}

// Coordinates are real (public geographic data); gradient pairs are the
// offline/loading fallback layer that sits underneath each photo.
export const DESTINATIONS: Destination[] = [
  {
    id: "tokyo",
    name: "Tokyo",
    country: "Japan",
    coords: "35.68°N 139.65°E",
    photo: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?q=80&w=900&auto=format&fit=crop",
    from: "#1B2735",
    to: "#2C1E2E",
  },
  {
    id: "rome",
    name: "Rome",
    country: "Italy",
    coords: "41.90°N 12.50°E",
    photo: "https://images.unsplash.com/photo-1552832230-c0197dd311b5?q=80&w=900&auto=format&fit=crop",
    from: "#2E1F14",
    to: "#3B2A16",
  },
  {
    id: "paris",
    name: "Paris",
    country: "France",
    coords: "48.86°N 2.35°E",
    photo: "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?q=80&w=900&auto=format&fit=crop",
    from: "#1E2430",
    to: "#33261C",
  },
  {
    id: "bali",
    name: "Bali",
    country: "Indonesia",
    coords: "8.34°S 115.09°E",
    photo: "https://images.unsplash.com/photo-1537996194471-e657df975ab4?q=80&w=900&auto=format&fit=crop",
    from: "#14291E",
    to: "#1E3326",
  },
  {
    id: "new-york",
    name: "New York",
    country: "USA",
    coords: "40.71°N 74.01°W",
    photo: "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?q=80&w=900&auto=format&fit=crop",
    from: "#151A24",
    to: "#232A38",
  },
  {
    id: "santorini",
    name: "Santorini",
    country: "Greece",
    coords: "36.39°N 25.46°E",
    photo: "https://images.unsplash.com/photo-1613395877344-13d4a8e0d49e?q=80&w=900&auto=format&fit=crop",
    from: "#16222E",
    to: "#1F3040",
  },
];

// Faint topographic contour pattern — keeps the "atlas" motif on the fallback layer.
const CONTOUR_SVG =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200' viewBox='0 0 200 200'%3E%3Cg fill='none' stroke='white' stroke-opacity='0.1'%3E%3Ccircle cx='100' cy='100' r='30'/%3E%3Ccircle cx='100' cy='100' r='60'/%3E%3Ccircle cx='100' cy='100' r='90'/%3E%3Ccircle cx='100' cy='100' r='120'/%3E%3C/g%3E%3C/svg%3E\")";

function DestinationCard({ dest }: { dest: Destination }) {
  return (
    <Link href="/login" className="shrink-0 snap-start" style={{ perspective: 1000 }}>
      <TiltCard
        intensity={9}
        glow
        className="group w-[250px] sm:w-[290px] h-[380px] rounded-2xl overflow-hidden border border-ink-900/10 shadow-lift hover:shadow-glow transition-shadow duration-300"
      >
        {/* Fallback gradient + contour — always painted underneath the photo */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `${CONTOUR_SVG}, linear-gradient(155deg, ${dest.from} 0%, ${dest.to} 100%)`,
            backgroundPosition: "center, center",
          }}
        />
        {/* Photo layer with slow zoom on hover */}
        <div
          className="absolute inset-0 bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-[1.06]"
          style={{ backgroundImage: `url(${dest.photo})` }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-black/10" />

        <div style={{ transform: "translateZ(40px)" }} className="relative z-10 h-full flex flex-col justify-end p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/60 mb-1.5">{dest.coords}</span>
          <h3 className="font-display text-3xl italic font-medium text-white leading-none mb-1.5">{dest.name}</h3>
          <div className="flex items-center justify-between">
            <span className="text-xs text-white/70">{dest.country}</span>
            <span className="w-7 h-7 rounded-full glass flex items-center justify-center group-hover:bg-sunset transition-colors duration-300">
              <ArrowUpRight className="w-3.5 h-3.5 text-white group-hover:text-[#1F1206] transition-colors duration-300" />
            </span>
          </div>
        </div>
      </TiltCard>
    </Link>
  );
}

export function DestinationScroll() {
  const trackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    // Let a vertical mouse-wheel gesture drive horizontal scroll — most desktop
    // users never discover shift+scroll, so this makes the row feel scrollable.
    // React's synthetic onWheel is passive by default, which silently drops
    // preventDefault(); attaching manually with { passive: false } is required
    // to actually stop the page from also scrolling vertically underneath.
    function handleWheel(e: WheelEvent) {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && el) {
        el.scrollLeft += e.deltaY;
        e.preventDefault();
      }
    }
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  function scrollBy(amount: number) {
    trackRef.current?.scrollBy({ left: amount, behavior: "smooth" });
  }

  return (
    <div className="relative">
      <div
        ref={trackRef}
        className="flex gap-5 overflow-x-auto snap-x snap-mandatory pb-4 scrollbar-hide px-4 sm:px-0"
        style={{ scrollPaddingLeft: 16 }}
      >
        {DESTINATIONS.map((dest) => (
          <DestinationCard key={dest.id} dest={dest} />
        ))}
      </div>

      {/* Nav arrows — desktop only, signal that the row scrolls */}
      <button
        onClick={() => scrollBy(-320)}
        aria-label="Scroll left"
        className="hidden sm:flex absolute -left-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full glass items-center justify-center text-ink-600 hover:text-accent hover:border-accent/40 transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>
      <button
        onClick={() => scrollBy(320)}
        aria-label="Scroll right"
        className="hidden sm:flex absolute -right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full glass items-center justify-center text-ink-600 hover:text-accent hover:border-accent/40 transition-colors"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
