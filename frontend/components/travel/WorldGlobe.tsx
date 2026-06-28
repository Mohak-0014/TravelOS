"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useState } from "react";
import Globe from "react-globe.gl";

/**
 * WorldGlobe — interactive 3D earth (three.js via react-globe.gl) with glowing
 * flight arcs from a home airport out to a handful of popular travel cities.
 * Auto-rotates, drag to spin. This component touches `window`/WebGL at module
 * load, so it must be imported with `next/dynamic({ ssr: false })` from parent.
 */

const HOME = { lat: 51.47, lng: -0.45 }; // London

interface Place {
  name: string;
  lat: number;
  lng: number;
  accent: string;
}

const PLACES: Place[] = [
  { name: "Tokyo", lat: 35.6762, lng: 139.6503, accent: "#fb7185" },
  { name: "Paris", lat: 48.8566, lng: 2.3522, accent: "#60a5fa" },
  { name: "New York", lat: 40.7128, lng: -74.006, accent: "#38bdf8" },
  { name: "Bali", lat: -8.4095, lng: 115.1889, accent: "#34d399" },
  { name: "Cape Town", lat: -33.9249, lng: 18.4241, accent: "#fbbf24" },
  { name: "Lisbon", lat: 38.7223, lng: -9.1393, accent: "#fda4af" },
  { name: "Reykjavík", lat: 64.1466, lng: -21.9426, accent: "#7dd3fc" },
  { name: "Marrakech", lat: 31.6295, lng: -7.9811, accent: "#fb923c" },
];

const ARCS = PLACES.map((p) => ({
  startLat: HOME.lat,
  startLng: HOME.lng,
  endLat: p.lat,
  endLng: p.lng,
  color: ["#fbbf24", p.accent] as [string, string],
}));

const POINTS = [{ ...HOME, name: "Home", accent: "#ffffff" }, ...PLACES];

export default function WorldGlobe() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<any>(null);
  const [size, setSize] = useState(0);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => setSize(entries[0].contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="relative flex w-full items-center justify-center">
      {/* ambient glow behind the globe */}
      <div className="pointer-events-none absolute h-[480px] w-[480px] rounded-full bg-electric-400/25 blur-[120px]" />
      <div className="pointer-events-none absolute h-72 w-72 rounded-full bg-gold-400/15 blur-[100px]" />

      <div ref={wrapRef} className="relative aspect-square w-full max-w-[560px]">
        {size > 0 && (
          <Globe
            ref={globeRef}
            width={size}
            height={size}
            backgroundColor="rgba(0,0,0,0)"
            globeImageUrl="https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
            bumpImageUrl="https://unpkg.com/three-globe/example/img/earth-topology.png"
            atmosphereColor="#7dd3fc"
            atmosphereAltitude={0.22}
            arcsData={ARCS}
            arcStartLat={(d: any) => d.startLat}
            arcStartLng={(d: any) => d.startLng}
            arcEndLat={(d: any) => d.endLat}
            arcEndLng={(d: any) => d.endLng}
            arcColor={(d: any) => d.color}
            arcStroke={0.5}
            arcDashLength={0.4}
            arcDashGap={0.18}
            arcDashAnimateTime={2600}
            arcAltitudeAutoScale={0.5}
            pointsData={POINTS}
            pointLat={(d: any) => d.lat}
            pointLng={(d: any) => d.lng}
            pointColor={(d: any) => d.accent}
            pointAltitude={0.015}
            pointRadius={0.45}
            labelsData={PLACES}
            labelLat={(d: any) => d.lat}
            labelLng={(d: any) => d.lng}
            labelText={(d: any) => d.name}
            labelSize={0.85}
            labelDotRadius={0.32}
            labelColor={() => "rgba(234,240,255,0.78)"}
            labelResolution={2}
            labelAltitude={0.012}
            onGlobeReady={() => {
              const g = globeRef.current;
              if (!g) return;
              const c = g.controls();
              c.autoRotate = true;
              c.autoRotateSpeed = 0.55;
              c.enableZoom = false;
              g.pointOfView({ lat: 18, lng: -10, altitude: 2.4 });
            }}
          />
        )}
      </div>
    </div>
  );
}
