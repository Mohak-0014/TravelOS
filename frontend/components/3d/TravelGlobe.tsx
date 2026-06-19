"use client";

import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";

interface GlobePoint {
  lat: number;
  lng: number;
  label: string;
  size?: number;
  color?: string;
}

interface TravelGlobeProps {
  points?: GlobePoint[];
  width?: number;
  height?: number;
}

// Dynamically loaded — react-globe.gl uses WebGL and can't SSR
const GlobeDynamic = dynamic(
  () =>
    import("react-globe.gl").then((m) => {
      const Globe = m.default;
      return function GlobeWrapper({ points, width, height }: TravelGlobeProps) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const globeRef = useRef<any>(undefined);

        useEffect(() => {
          if (!globeRef.current) return;
          // Auto-rotate
          globeRef.current.controls().autoRotate = true;
          globeRef.current.controls().autoRotateSpeed = 0.6;
          globeRef.current.controls().enableZoom = false;
          globeRef.current.pointOfView({ lat: 20, lng: 0, altitude: 2 }, 0);
        }, []);

        const defaultPoints: GlobePoint[] =
          points && points.length > 0
            ? points
            : [
                { lat: 48.8566, lng: 2.3522, label: "Paris", size: 0.6, color: "#60a5fa" },
                { lat: 35.6762, lng: 139.6503, label: "Tokyo", size: 0.6, color: "#f59e0b" },
                { lat: 40.7128, lng: -74.006, label: "New York", size: 0.6, color: "#34d399" },
                { lat: -33.8688, lng: 151.2093, label: "Sydney", size: 0.5, color: "#a78bfa" },
                { lat: 51.5074, lng: -0.1278, label: "London", size: 0.6, color: "#fb7185" },
                { lat: 25.2048, lng: 55.2708, label: "Dubai", size: 0.5, color: "#fbbf24" },
              ];

        return (
          <Globe
            ref={globeRef}
            width={width ?? 380}
            height={height ?? 380}
            backgroundColor="rgba(0,0,0,0)"
            globeImageUrl="//unpkg.com/three-globe/example/img/earth-dark.jpg"
            bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
            atmosphereColor="#3b82f6"
            atmosphereAltitude={0.2}
            pointsData={defaultPoints}
            pointLat="lat"
            pointLng="lng"
            pointLabel="label"
            pointColor={(d: unknown) => (d as GlobePoint).color ?? "#60a5fa"}
            pointAltitude={0.02}
            pointRadius={(d: unknown) => (d as GlobePoint).size ?? 0.5}
            pointsMerge={false}
          />
        );
      };
    }),
  { ssr: false, loading: () => <div className="w-[380px] h-[380px] rounded-full bg-space-700/30 animate-pulse" /> }
);

export default function TravelGlobe(props: TravelGlobeProps) {
  return <GlobeDynamic {...props} />;
}
