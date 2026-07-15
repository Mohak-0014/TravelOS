"use client";

import { useEffect, useRef } from "react";
import createGlobe from "cobe";
import { cn } from "@/lib/ui";

export interface GlobeMarker {
  location: [number, number];
  size: number;
}

export interface GlobeProps {
  markers?: GlobeMarker[];
  size?: number;
  className?: string;
  /** Start rotated so this [lat, lng] faces the viewer — e.g. the user's trips.
   * Without it the globe opens on the default equatorial view. */
  focus?: [number, number];
}

// From cobe's "rotate to location" example: converts lat/lng into the phi/theta
// pair that puts that point front-and-center.
function locationToAngles(lat: number, lng: number): [number, number] {
  return [Math.PI - ((lng * Math.PI) / 180 - Math.PI / 2), (lat * Math.PI) / 180];
}

// Night Flight palette as 0–1 RGB triples (cobe takes floats, not hex).
const BASE_COLOR: [number, number, number] = [0.55, 0.6, 0.68]; // cool slate landmass dots
const MARKER_COLOR: [number, number, number] = [1.0, 0.62, 0.39]; // sunset accent #FF9E64
const GLOW_COLOR: [number, number, number] = [0.09, 0.11, 0.15]; // subtle cool halo into bg

/** Interactive drag-to-rotate 3D globe (cobe — 5KB canvas/WebGL, zero deps). */
export function Globe({ markers = [], size = 400, className, focus }: GlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const initialAngles = focus ? locationToAngles(focus[0], focus[1]) : null;
  const phi = useRef(initialAngles?.[0] ?? 0);
  const theta = useRef(initialAngles?.[1] ?? 0.3);
  const width = useRef(0);
  const pointerInteracting = useRef<number | null>(null);
  const pointerInteractionMovement = useRef(0);
  const rotation = useRef(0);

  const markersKey = JSON.stringify(markers);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    let globe: ReturnType<typeof createGlobe> | null = null;
    let destroyed = false;

    // A single synchronous offsetWidth read can race with layout — especially
    // for a globe mounted below the fold or inside an animating (whileInView)
    // parent — and silently leaves the canvas at the browser's 300x150
    // fallback size. ResizeObserver guarantees we only initialize once the
    // container has a real, laid-out size.
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width || container.offsetWidth;
      if (w <= 0 || destroyed) return;
      width.current = w;

      if (!globe) {
        globe = createGlobe(canvas, {
          devicePixelRatio: 2,
          width: w * 2,
          height: w * 2,
          phi: phi.current,
          theta: theta.current,
          dark: 1,
          diffuse: 1.2,
          scale: 1.05,
          mapSamples: 12000,
          mapBrightness: 7,
          mapBaseBrightness: 0.05,
          baseColor: BASE_COLOR,
          markerColor: MARKER_COLOR,
          glowColor: GLOW_COLOR,
          markers: JSON.parse(markersKey),
          onRender: (state) => {
            if (pointerInteracting.current === null) phi.current += 0.0028;
            state.phi = phi.current + rotation.current;
            state.width = width.current * 2;
            state.height = width.current * 2;
          },
        });
        requestAnimationFrame(() => {
          if (canvas) canvas.style.opacity = "1";
        });
      }
    });
    ro.observe(container);

    return () => {
      destroyed = true;
      ro.disconnect();
      globe?.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markersKey]);

  const updatePointerInteraction = (value: number | null) => {
    pointerInteracting.current = value;
    if (canvasRef.current) canvasRef.current.style.cursor = value !== null ? "grabbing" : "grab";
  };

  const updateMovement = (clientX: number) => {
    if (pointerInteracting.current === null) return;
    const delta = clientX - pointerInteracting.current;
    pointerInteractionMovement.current = delta;
    rotation.current = delta / 200;
  };

  return (
    <div ref={containerRef} style={{ width: size, height: size }} className={cn("relative mx-auto", className)}>
      <canvas
        ref={canvasRef}
        onPointerDown={(e) => {
          pointerInteracting.current = e.clientX - pointerInteractionMovement.current;
          updatePointerInteraction(e.clientX - pointerInteractionMovement.current);
        }}
        onPointerUp={() => updatePointerInteraction(null)}
        onPointerOut={() => updatePointerInteraction(null)}
        onMouseMove={(e) => updateMovement(e.clientX)}
        onTouchMove={(e) => e.touches[0] && updateMovement(e.touches[0].clientX)}
        style={{
          width: "100%",
          height: "100%",
          cursor: "grab",
          contain: "layout paint size",
          opacity: 0,
          transition: "opacity 0.6s ease",
        }}
      />
    </div>
  );
}
